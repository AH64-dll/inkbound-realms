"""Generic deterministic RPG rules. Books and AI providers never enter this module."""
from __future__ import annotations

import os
import random
import tempfile
from collections import deque
from pathlib import Path

from inkbound.realm.models import Action, Ability, Condition, Effect, EnemyArchetype, PlayerDefinition
from inkbound.realm.package import RealmPackage, canonical
from inkbound.runtime.maps import MapData, build_maps, connect, stable_seed
from inkbound.runtime.state import ActorState, SaveGame, LootDrop


class Engine:
    def __init__(self, package: RealmPackage, state: SaveGame | None = None, seed: int | None = None):
        self.package = package
        self.spec = package.spec
        self.index = self.spec.index()
        self.rules = self.spec.world_rules
        self.health_id = self.rules.health_resource_id
        if state is not None:
            if state.package_digest != package.digest:
                raise ValueError("Save belongs to a different realm revision; use its original package")
            self.state = state
            self._validate_save()
            return
        maps = build_maps(self.spec)
        definition = self.spec.player
        start = self.index[definition.starting_location_id]
        player = self._actor(definition, definition.id, start.region_id, start.x, start.y)
        self.state = SaveGame(package_digest=package.digest, seed=self.spec.metadata.seed if seed is None else seed,
                              player=player, maps=maps, inventory=dict(definition.starting_items), gold=self.spec.economy.starting_gold,
                              visited=[start.id], quests_known=[q.id for q in self.spec.quests if q.discovered],
                              quest_start_turns={q.id: 0 for q in self.spec.quests if q.discovered},
                              annals=[f"Year {h.year}: {h.event}" for h in self.spec.history])
        for key in sorted(self.state.inventory):
            item = self.index[key]
            if item.slot_id and item.slot_id not in self.state.equipment:
                self.equip(key)
        for npc in self.spec.npcs:
            m = maps.get(self.npc_map_id(npc))
            if m:
                center = m.points.get(npc.location_id, [len(m.grid[0]) // 2, len(m.grid) // 2])
                candidates = sorted(m.reachable(), key=lambda xy: (abs(xy[0] - center[0]) + abs(xy[1] - center[1]), xy))
                occupied = {tuple(v) for k, v in self.state.npc_positions.items() if self.npc_map_id(self.index[k]) == m.id}
                xy = next(p for p in candidates if p not in occupied and p != tuple(m.entrance))
                self.state.npc_positions[npc.id] = list(xy)
        self.log(f"{self.spec.metadata.title}: {definition.name}, {definition.archetype}.")
        self.log("Explore, listen to the guide, and follow the known tales. The realm runs offline.")
        self._spawn_encounters()

    def _actor(self, definition: PlayerDefinition | EnemyArchetype, actor_id: str, map_id: str, x: int, y: int) -> ActorState:
        return ActorState(id=actor_id, definition_id=definition.id, map_id=map_id, x=x, y=y,
                          stats=dict(definition.stats), resources=dict(definition.resources), caps=dict(definition.resources), abilities=list(definition.ability_ids))

    @property
    def player(self):
        return self.state.player

    @property
    def current_map(self):
        return self.state.maps[self.player.map_id]

    def npc_map_id(self, npc):
        return npc.location_id if npc.location_id in self.state.maps else self.index[npc.location_id].region_id

    def npc_available(self, npc):
        loc = self.index[npc.location_id]
        return loc.id in self.state.unlocked or self.conditions(loc.locked_by)

    def log(self, message: str):
        self.state.messages.append(message)
        self.state.messages = self.state.messages[-80:]

    def rng(self) -> random.Random:
        result = random.Random(stable_seed(self.state.seed, self.state.rng_counter))
        self.state.rng_counter += 1
        return result

    def alive(self, actor: ActorState) -> bool:
        return actor.resources.get(self.health_id, 0) > 0 and not actor.defeated

    def restrained(self) -> bool:
        if any(self.index[sid].skip_turn for sid in self.player.statuses):
            self.log("The restraint holds you for this turn.")
            self.tick()
            return True
        return False

    def stat(self, actor: ActorState, key: str) -> int:
        value = actor.stats.get(key, 0)
        if actor is self.player:
            value += sum(self.index[i].stat_mods.get(key, 0) for i in self.state.equipment.values())
            cls, species = self.spec.player.class_id, self.spec.player.species_id
            value += sum(self.index[eid].stat_mods.get(key, 0) for eid in [cls, species] if eid)
            value += sum(p.stat_mods.get(key, 0) for p in self.spec.player.passives if p.trigger == "always")
        value += sum(self.index[sid].stat_mods.get(key, 0) for sid in actor.statuses)
        definition = self.index[key]
        return max(definition.minimum, min(definition.maximum, value))

    def known_abilities(self) -> list[str]:
        cls = self.spec.player.class_id
        class_abilities = self.index[cls].ability_ids if cls else []
        return list(dict.fromkeys(self.player.abilities + self.spec.player.interaction_ability_ids + class_abilities + [a for slot, i in sorted(self.state.equipment.items()) for a in self.index[i].ability_ids]))

    def passive_event(self, trigger: str):
        if not self.alive(self.player):
            return
        for passive in self.spec.player.passives:
            if passive.trigger == trigger:
                for rid, amount in passive.resource_gain.items():
                    self.player.resources[rid] = min(self.player.caps[rid], self.player.resources[rid] + amount)

    def conditions(self, conditions: list[Condition]) -> bool:
        s = self.state
        for c in conditions:
            result = {"quest_done": lambda: c.target in s.quests_done,
                      "quest_active": lambda: c.target in self.active_quests(),
                      "item": lambda: self.item_count(c.target) >= c.amount,
                      "standing": lambda: s.standing.get(c.target, 0) >= c.amount,
                      "flag": lambda: s.flags.get(c.target, 0) >= c.amount,
                      "level": lambda: s.level >= c.amount,
                      "visited": lambda: c.target in s.visited,
                      "kills": lambda: s.kills.get(c.target, 0) >= c.amount,
                      "turn": lambda: s.turn >= c.amount}[c.kind]()
            if result == c.negate:
                return False
        return True

    def active_quests(self) -> list[str]:
        s = self.state
        return [q.id for q in self.spec.quests if q.id in s.quests_known and q.id not in s.quests_done + s.quests_failed
                and set(q.prerequisites) <= set(s.quests_done)]

    def quest_progress(self, quest_id: str) -> list[int]:
        result = []
        for obj in self.index[quest_id].objectives:
            kind, eid = obj.kind, obj.target_id
            value = {"visit": lambda: int(eid in self.state.visited), "kill": lambda: self.state.kills.get(eid, 0),
                     "talk": lambda: int(eid in self.state.talked), "collect": lambda: self.item_count(eid),
                     "craft": lambda: self.state.crafted.get(eid, 0), "pay": lambda: self.state.gold if eid in self.state.visited else 0,
                     "escort": lambda: int(self.state.flags.get("escort." + eid, 0) > 0 and obj.destination_id in self.state.visited),
                     "choice": lambda: int(any(x.startswith(eid + ":") for x in self.state.dialogue_choices))}[kind]()
            result.append(min(obj.count, value))
        return result

    def grant_actions(self, actions: list[Action]):
        for a in actions:
            if a.kind == "grant_item":
                self.add_item(a.target, a.amount)
            elif a.kind == "gold":
                self.state.gold = max(0, self.state.gold + a.amount)
            elif a.kind == "xp":
                self.gain_xp(a.amount)
            elif a.kind == "standing":
                self.state.standing[a.target] = self.state.standing.get(a.target, 0) + a.amount
            elif a.kind == "flag":
                self.state.flags[a.target] = a.amount
            elif a.kind == "unlock":
                if a.target not in self.state.unlocked:
                    self.state.unlocked.append(a.target)
            elif a.kind == "heal":
                self.player.resources[a.target] = min(self.player.caps.get(a.target, 0), self.player.resources.get(a.target, 0) + a.amount)
            elif a.kind == "start_quest":
                self.discover_quest(a.target)
            elif a.kind == "spawn":
                self.spawn(a.target, self.player.map_id, a.amount, "event", self.state.turn)

    def discover_quest(self, quest_id):
        if quest_id not in self.state.quests_known:
            self.state.quests_known.append(quest_id)
            self.state.quest_start_turns[quest_id] = self.state.turn
            self.log(f"Heard: {self.index[quest_id].name}")

    def turn_in(self, npc_id: str) -> list[str]:
        completed = []
        # Recompute between turn-ins so an arc can move forward on a single visit.
        for q in self.spec.quests:
            if q.id not in self.active_quests() or q.giver_id != npc_id:
                continue
            progress = self.quest_progress(q.id)
            if not all(n >= obj.count for n, obj in zip(progress, q.objectives)):
                continue
            # Check all consumable objectives jointly before charging anything.
            needed: dict[str, int] = {}
            gold_cost = 0
            for obj in q.objectives:
                if obj.kind == "collect" and obj.consume:
                    needed[obj.target_id] = needed.get(obj.target_id, 0) + obj.count
                if obj.kind == "pay":
                    gold_cost += obj.count
            if self.state.gold < gold_cost or any(self.item_count(eid) < count for eid, count in needed.items()):
                continue
            for eid, count in needed.items():
                self.remove_item(eid, count)
            self.state.gold -= gold_cost
            self.state.quests_done.append(q.id)
            self.state.annals.append(f"Day {self.day}: {self.player_name} completed {q.name}.")
            self.grant_actions(q.reward_actions)
            self.log(f"Tale complete: {q.name}")
            completed.append(q.id)
            for follow in self.spec.quests:
                if q.id in follow.prerequisites and set(follow.prerequisites) <= set(self.state.quests_done):
                    self.discover_quest(follow.id)
        return completed

    @property
    def player_name(self):
        return self.spec.player.name

    @property
    def day(self):
        return self.state.turn // self.rules.turns_per_day + 1

    def item_count(self, item_id):
        return self.state.inventory.get(item_id, 0) + list(self.state.equipment.values()).count(item_id)

    def add_item(self, item_id: str, count: int, *, defer=True, at=None):
        if sum(self.state.inventory.values()) + count > self.rules.inventory_capacity:
            if defer:
                at = at or self.player
                key = f"{at.map_id}:{at.x}:{at.y}"
                drop = self.state.pending_loot.setdefault(key, LootDrop(map_id=at.map_id, x=at.x, y=at.y, items={}))
                drop.items[item_id] = drop.items.get(item_id, 0) + count
                self.log(f"Pack full: {self.index[item_id].name} waits at ({at.x}, {at.y}). E collects it when space is free.")
            else:
                self.log("Pack full.")
            return False
        self.state.inventory[item_id] = self.state.inventory.get(item_id, 0) + count
        self.log(f"Obtained {count} {self.index[item_id].name}.")
        return True

    def collect_loot(self):
        if not self.alive(self.player): return False
        nearby = [(key, drop) for key, drop in self.state.pending_loot.items() if drop.map_id == self.player.map_id and abs(drop.x - self.player.x) + abs(drop.y - self.player.y) <= 1]
        if not nearby: return False
        for key, drop in sorted(nearby):
            for item_id, count in sorted(drop.items.items()):
                room = self.rules.inventory_capacity - sum(self.state.inventory.values())
                n = min(count, room)
                if n > 0:
                    self.add_item(item_id, n, defer=False)
                    drop.items[item_id] -= n
                    if not drop.items[item_id]: del drop.items[item_id]
            if not drop.items: del self.state.pending_loot[key]
        if any(key in self.state.pending_loot for key, _ in nearby): self.log("Free pack space to collect any remaining finds.")
        return True

    def reserved_item_count(self, item_id):
        consuming = 0; retained = 0
        for quest in self.spec.quests:
            if quest.main and quest.id not in self.state.quests_done + self.state.quests_failed:
                for obj in quest.objectives:
                    if obj.kind == "collect" and obj.target_id == item_id:
                        if obj.consume: consuming += obj.count
                        else: retained = max(retained, obj.count)
        return consuming + retained

    def remove_item(self, item_id, count):
        if count > self.item_count(item_id):
            return False
        n = min(count, self.state.inventory.get(item_id, 0))
        self.state.inventory[item_id] = self.state.inventory.get(item_id, 0) - n
        if not self.state.inventory[item_id]:
            del self.state.inventory[item_id]
        for slot, eid in list(self.state.equipment.items()):
            if n < count and eid == item_id:
                del self.state.equipment[slot]; n += 1
        return True

    def equip(self, item_id: str) -> bool:
        item = self.index.get(item_id)
        if not item or not item.slot_id or item.slot_id not in self.spec.player.equipment_slots or self.state.inventory.get(item_id, 0) < 1:
            return False
        old = self.state.equipment.get(item.slot_id)
        self.state.inventory[item_id] -= 1
        if not self.state.inventory[item_id]:
            del self.state.inventory[item_id]
        if old:
            self.state.inventory[old] = self.state.inventory.get(old, 0) + 1
        self.state.equipment[item.slot_id] = item_id
        self.log(f"Equipped {item.name}.")
        return True

    def unequip(self, slot_id: str) -> bool:
        if slot_id not in self.state.equipment or sum(self.state.inventory.values()) >= self.rules.inventory_capacity:
            return False
        eid = self.state.equipment.pop(slot_id)
        self.state.inventory[eid] = self.state.inventory.get(eid, 0) + 1
        return True

    def gain_xp(self, amount: int):
        self.state.xp += amount
        prog = self.index[self.spec.player.progression_id]
        while self.state.xp >= self.state.level * prog.xp_per_level:
            self.state.xp -= self.state.level * prog.xp_per_level
            self.state.level += 1
            for key, amount in prog.stat_growth.items():
                self.player.stats[key] = min(self.index[key].maximum, self.player.stats.get(key, 0) + amount)
            for key, amount in prog.resource_growth.items():
                if key in self.player.caps:
                    self.player.caps[key] += amount
                    self.player.resources[key] = min(self.player.caps[key], self.player.resources.get(key, 0) + amount)
            for aid in prog.unlocks.get(str(self.state.level), []):
                if aid not in self.player.abilities:
                    self.player.abilities.append(aid)
            self.log(f"Level {self.state.level}: your tools and confidence improve.")

    def train(self, action: str):
        prog = self.index[self.spec.player.progression_id]
        for sid in prog.skill_ids:
            skill = self.index[sid]
            if skill.training_action != action:
                continue
            self.state.skills[sid] = self.state.skills.get(sid, 0) + 1
            if sid not in self.state.mastered_skills and self.state.skills[sid] >= skill.threshold and set(skill.prerequisites) <= set(self.state.mastered_skills):
                self.state.mastered_skills.append(sid)
                for aid in skill.ability_ids:
                    if aid not in self.player.abilities:
                        self.player.abilities.append(aid)
                for key, value in skill.stat_mods.items():
                    self.player.stats[key] = max(self.index[key].minimum, min(self.index[key].maximum, self.player.stats.get(key, 0) + value))
                self.log(f"Practice mastered: {skill.name}.")

    def location_here(self):
        key = self.player.map_id.split(":")[0]
        if key in {loc.id for loc in self.spec.locations}:
            return self.index[key]
        for loc in self.spec.locations:
            if loc.region_id == key and self.current_map.points.get(loc.id) == [self.player.x, self.player.y]:
                return loc
        return None

    def move(self, dx: int, dy: int) -> bool:
        if not self.alive(self.player) or abs(dx) + abs(dy) != 1 or self.state.active_dialogue_id:
            return False
        if self.restrained():
            return True
        x, y = self.player.x + dx, self.player.y + dy
        if not self.player_walkable(self.player.map_id, x, y):
            self.log("Blocked."); return False
        if any(a.map_id == self.player.map_id and a.x == x and a.y == y and self.alive(a) and not a.friendly for a in self.state.actors.values()):
            self.log("A threat holds that tile. Attack, offer terms or retreat."); return False
        self.player.x, self.player.y = x, y
        region_ids = {r.id for r in self.spec.regions}
        if self.player.map_id in region_ids:
            loc = self.location_here()
            if loc:
                self.visit(loc.id)
            self.train("explore")
            self._maybe_expand()
        elif self.current_map.grid[y][x] == "G":
            self.leave()
        self._companions_follow()
        self.tick()
        return True

    def player_walkable(self, map_id, x, y):
        m = self.state.maps[map_id]
        if not 0 <= y < len(m.grid) or not 0 <= x < len(m.grid[0]): return False
        definition = self.index.get(map_id)
        water = m.grid[y][x] == "~" or (getattr(definition, "generator", None) == "nautical" and m.grid[y][x] == ",")
        if water: return self.spec.player.movement in ("sail", "hover")
        return m.walkable(x, y)

    def actor_walkable(self, actor, x, y):
        if actor is self.player or actor.friendly and actor.definition_id in {n.id for n in self.spec.npcs}:
            return self.player_walkable(actor.map_id, x, y)
        return self.state.maps[actor.map_id].walkable(x, y)

    def _maybe_expand(self):
        region = self.index.get(self.player.map_id)
        if self.player.map_id not in {r.id for r in self.spec.regions} or not region.frontier:
            return
        m = self.current_map; width, height = len(m.grid[0]), len(m.grid)
        if self.player.x <= 2: self.expand("left")
        elif self.player.x >= width - 3: self.expand("right")
        elif self.player.y <= 2: self.expand("top")
        elif self.player.y >= height - 3: self.expand("bottom")

    def expand(self, side: str, size: int = 16) -> bool:
        """Grow global terrain without changing any authored content ID."""
        region = self.index.get(self.player.map_id)
        if self.player.map_id not in {r.id for r in self.spec.regions} or not region.frontier or side not in ("left", "right", "top", "bottom"):
            return False
        from legacy.ascii_rpg.src.worldgen import gen_strip
        m = self.current_map; width, height = len(m.grid[0]), len(m.grid)
        x0, y0 = m.origin
        sx, sy = (size if side == "left" else 0), (size if side == "top" else 0)
        strip_w, strip_h = (size, height) if side in ("left", "right") else (width, size)
        strip_x = x0 - size if side == "left" else x0 + width if side == "right" else x0
        strip_y = y0 - size if side == "top" else y0 + height if side == "bottom" else y0
        if region.generator == "station":
            strip = [["#" if (x + strip_x) % 9 == 6 and (y + strip_y) % 7 != 0 else "." for x in range(strip_w)] for y in range(strip_h)]
        else:
            strip = gen_strip(m.terrain_seed, m.thresholds, strip_x, strip_y, strip_w, strip_h)
            if region.generator == "nautical":
                strip = [["," if c == "~" else "." if c in ",rs=" else "T" for c in row] for row in strip]
        grid = [list(row) for row in m.grid]
        if side == "left": grid = [s + r for s, r in zip(strip, grid)]
        elif side == "right": grid = [r + s for r, s in zip(grid, strip)]
        elif side == "top": grid = strip + grid
        else: grid += strip
        for actor in [self.player, *self.state.actors.values()]:
            if actor.map_id == m.id:
                actor.x += sx; actor.y += sy
        for drop in self.state.pending_loot.values():
            if drop.map_id == m.id: drop.x += sx; drop.y += sy
        for npc in self.spec.npcs:
            if self.npc_map_id(npc) == m.id and npc.id in self.state.npc_positions:
                xy = self.state.npc_positions[npc.id]
                xy[0] += sx; xy[1] += sy
        m.entrance = [m.entrance[0] + sx, m.entrance[1] + sy]
        m.points = {eid: [xy[0] + sx, xy[1] + sy] for eid, xy in m.points.items()}
        m.origin = [x0 - sx, y0 - sy]
        for spot in self.state.return_stack:
            if spot["map_id"] == m.id:
                spot["x"] += sx; spot["y"] += sy
        # An accessible frontier refuge is a procedural landmark, not an AI entity.
        fx = size // 2 if side == "left" else width + size // 2 if side == "right" else self.player.x
        fy = size // 2 if side == "top" else height + size // 2 if side == "bottom" else self.player.y
        connect(grid, (self.player.x, self.player.y), (fx, fy))
        grid[fy][fx] = "*"
        m.grid = ["".join(row) for row in grid]
        self.log(f"The frontier opens beyond {region.name}. A new road reaches a quiet refuge.")
        return True

    def visit(self, location_id):
        if location_id not in self.state.visited:
            self.state.visited.append(location_id)
            loc = self.index[location_id]
            self.log(f"Discovered {loc.name}. {loc.lore}")
            self.grant_actions(loc.entry_actions)
            self.gain_xp(5)
            self.passive_event("on_visit")

    def enter(self, location_id: str | None = None) -> bool:
        if not self.alive(self.player):
            return False
        loc = self.index.get(location_id) if location_id else self.location_here()
        if not loc or not hasattr(loc, "kind") or loc.id not in {x.id for x in self.spec.locations}:
            return False
        if self.player.map_id != loc.region_id or self.current_map.points.get(loc.id) != [self.player.x, self.player.y]:
            return False
        if loc.id not in self.state.unlocked and not self.conditions(loc.locked_by):
            self.log(f"{loc.name} is closed. Follow the quest arc to open it."); return False
        self.visit(loc.id)
        if loc.kind in ("settlement", "dungeon", "ruin"):
            self.state.return_stack.append({"map_id": self.player.map_id, "x": self.player.x, "y": self.player.y})
            self.player.map_id = loc.id
            self.player.x, self.player.y = self.current_map.entrance
            self._spawn_encounters()
            self.log(f"Entered {loc.name}. {loc.lore}")
        elif loc.kind in ("farm", "shrine"):
            key = f"rest.{loc.id}.{self.day}"
            if not self.state.flags.get(key):
                self.player.resources[self.health_id] = min(self.player.caps[self.health_id], self.player.resources[self.health_id] + 12)
                self.state.flags[key] = 1
                self.log("The refuge offers a little recovery and a lesson from the past.")
        elif loc.kind == "tower":
            self.log("From the tower you see " + ", ".join(x.name for x in self.spec.locations if x.region_id == loc.region_id))
        else:
            self.log(loc.lore)
        return True

    def leave(self) -> bool:
        if not self.state.return_stack:
            return False
        spot = self.state.return_stack.pop()
        self.player.map_id = spot["map_id"]
        self.player.x, self.player.y = spot["x"], spot["y"]
        self.state.active_dialogue_id = self.state.active_dialogue_node = self.state.active_npc_id = None
        self.state.target_id = None
        self.log("Returned to the road.")
        return True

    def change_floor(self, direction: int) -> bool:
        loc = self.location_here()
        if not loc or loc.kind not in ("dungeon", "ruin"):
            return False
        glyph = self.current_map.grid[self.player.y][self.player.x]
        if direction > 0 and glyph != ">" or direction < 0 and glyph != "<":
            return False
        floor = self.current_map.floor + direction
        if floor < 0:
            return self.leave()
        if floor >= loc.depth:
            return False
        key = loc.id if floor == 0 else f"{loc.id}:{floor}"
        self.player.map_id = key
        point = self.current_map.entrance if direction > 0 else self.current_map.exit or self.current_map.entrance
        self.player.x, self.player.y = point
        self._spawn_encounters()
        self.log(f"{loc.name}, floor {floor + 1}/{loc.depth}.")
        return True

    def interact(self):
        if not self.alive(self.player): return False
        if self.collect_loot():
            return True
        if self.state.active_dialogue_id:
            return False
        for npc in self.spec.npcs:
            xy = self.state.npc_positions.get(npc.id)
            if self.npc_map_id(npc) == self.player.map_id and self.npc_available(npc) and xy and abs(xy[0] - self.player.x) + abs(xy[1] - self.player.y) <= 1:
                return self.talk(npc.id)
        if self.player.map_id in {r.id for r in self.spec.regions}:
            if self.location_here() is None and self.current_map.grid[self.player.y][self.player.x] == "*":
                key = f"refuge.{self.player.map_id}.{self.player.x + self.current_map.origin[0]}.{self.player.y + self.current_map.origin[1]}.{self.day}"
                if key not in self.state.flags:
                    self.state.flags[key] = 1
                    self.player.resources[self.health_id] = min(self.player.caps[self.health_id], self.player.resources[self.health_id] + 12)
                    self.log("The frontier refuge offers a quiet meal and shelter.")
                return True
            return self.enter()
        glyph = self.current_map.grid[self.player.y][self.player.x]
        if glyph == "<":
            return self.change_floor(-1)
        if glyph == ">":
            return self.change_floor(1)
        if glyph == "C":
            key = f"{self.player.map_id}:{self.player.x}:{self.player.y}"
            if key not in self.state.opened_chests:
                self.state.opened_chests.append(key)
                self.state.gold += 5 + self.rng().randrange(8)
                materials = [i for i in self.spec.items if i.kind == "material"]
                if materials:
                    self.add_item(materials[self.rng().randrange(len(materials))].id, 1)
                self.log("Recovered a small forgotten cache.")
                return True
        self.log("No one answers here.")
        return False

    def talk(self, npc_id):
        npc = self.index.get(npc_id)
        xy = self.state.npc_positions.get(npc_id)
        if not npc or not xy or not self.alive(self.player) or self.npc_map_id(npc) != self.player.map_id or not self.npc_available(npc) or abs(xy[0] - self.player.x) + abs(xy[1] - self.player.y) > 1:
            return False
        if npc_id not in self.state.talked:
            self.state.talked.append(npc_id)
        practice_key = f"practice.talk.{npc_id}.{self.day}"
        if not self.state.flags.get(practice_key):
            self.state.flags[practice_key] = 1
            self.train("talk")
        for quest in self.spec.quests:
            if quest.giver_id == npc_id and set(quest.prerequisites) <= set(self.state.quests_done):
                self.discover_quest(quest.id)
        for quest in self.spec.quests:
            if quest.id in self.active_quests():
                for obj in quest.objectives:
                    if obj.kind == "escort" and obj.target_id == npc_id and not self.state.flags.get("escort." + npc_id):
                        self.state.companions[npc_id] = obj.destination_id
                        aid = "companion:" + npc_id
                        if aid not in self.state.actors:
                            stats = npc.stats or self.spec.player.stats
                            caps = npc.resources or {rid: max(1, cap // 2) for rid, cap in self.player.caps.items()}
                            self.state.actors[aid] = ActorState(id=aid, definition_id=npc.id, map_id=self.player.map_id,
                                                                x=xy[0], y=xy[1], stats=dict(stats), resources=dict(caps), caps=dict(caps),
                                                                abilities=list(npc.ability_ids or [self.rules.default_ability_id]), friendly=True)
        self.turn_in(npc_id)
        self.state.active_npc_id = npc_id
        self.state.active_dialogue_id = npc.dialogue_id
        self.state.active_dialogue_node = self.index[npc.dialogue_id].start_node_id
        self.log(f"{npc.name}: {self.dialogue_node().text}")
        return True

    def dialogue_node(self):
        if not self.state.active_dialogue_id:
            return None
        return next(n for n in self.index[self.state.active_dialogue_id].nodes if n.id == self.state.active_dialogue_node)

    def choose(self, choice_id):
        node = self.dialogue_node()
        if not node:
            return False
        choice = next((c for c in node.choices if c.id == choice_id), None)
        if not choice or not self.conditions(choice.conditions):
            return False
        key = self.state.active_dialogue_id + ":" + choice.id
        self.state.dialogue_choices.append(key)
        self.grant_actions(choice.actions)
        if choice.next_node_id:
            self.state.active_dialogue_node = choice.next_node_id
            self.log(self.dialogue_node().text)
        else:
            self.close_dialogue()
        return True

    def close_dialogue(self):
        self.state.active_dialogue_id = self.state.active_dialogue_node = self.state.active_npc_id = None

    def _companions_follow(self):
        loc = self.location_here()
        for npc_id, destination in list(self.state.companions.items()):
            actor = self.state.actors.get("companion:" + npc_id)
            if actor is None or not self.alive(actor):
                continue
            if actor.map_id != self.player.map_id:
                actor.map_id = self.player.map_id
                actor.x, actor.y = self.player.x, self.player.y
            elif self.distance(actor, self.player) > 1:
                self.step_toward(actor, self.player)
            if loc and self.distance(actor, self.player) <= 2:
                if loc.id == destination:
                    self.state.flags["escort." + npc_id] = 1
                    del self.state.companions[npc_id]
                    del self.state.actors[actor.id]
                    self.log(f"{self.index[npc_id].name} reaches {loc.name} safely.")

    def rest(self):
        if not self.alive(self.player):
            return False
        loc = self.location_here()
        safe = loc is not None and loc.kind == "settlement"
        cost = self.spec.economy.rest_price if safe else 0
        if self.state.gold < cost:
            self.log("Not enough currency for the inn."); return False
        self.state.gold -= cost
        for _ in range(6):
            self.tick(enemies=not safe)
            if not self.alive(self.player):
                return False
        for key in self.player.resources:
            self.player.resources[key] = self.player.caps[key] if safe else min(self.player.caps[key], self.player.resources[key] + 12)
        self.player.statuses.clear(); self.player.winded = False
        if safe:
            for npc_id in self.state.companions:
                actor = self.state.actors.get("companion:" + npc_id)
                if actor:
                    actor.defeated = False; actor.resources = dict(actor.caps); actor.statuses.clear()
                    actor.map_id = self.player.map_id; actor.x, actor.y = self.player.x, self.player.y
        self.passive_event("on_rest")
        self.train("rest"); self.log("Rested at the hearth." if safe else "Rested on the road; the wilds did not stop.")
        return True

    def heal(self):
        loc = self.location_here()
        if not self.alive(self.player) or not loc or loc.kind != "settlement" or self.state.gold < self.spec.economy.heal_price:
            return False
        self.state.gold -= self.spec.economy.heal_price
        self.player.resources[self.health_id] = self.player.caps[self.health_id]
        self.player.statuses.clear(); self.log("The settlement tends your injuries.")
        return True

    def price(self, item_id, buying=True):
        item = self.index[item_id]
        loc = self.location_here()
        multiplier = 100
        if loc and item.kind in ("material", "consumable"):
            multiplier = random.Random(stable_seed(self.state.seed, loc.id, item_id, self.day // 3)).choice([90, 100, 110])
        if not buying:
            multiplier = min(multiplier, 100) * self.spec.economy.sell_percent // 100
        return max(1, item.price * multiplier // 100)

    def buy(self, item_id):
        loc = self.location_here()
        if not loc or loc.kind != "settlement" or item_id not in loc.market_items or not self.alive(self.player):
            return False
        cost = self.price(item_id)
        stock_key = f"stock.{loc.id}.{item_id}"
        bought = self.state.flags.get(stock_key, 0)
        if bought >= loc.market_items[item_id] or self.state.gold < cost:
            return False
        if not self.add_item(item_id, 1, defer=False):
            return False
        self.state.gold -= cost; self.state.flags[stock_key] = bought + 1
        return True

    def sell(self, item_id):
        loc = self.location_here()
        if not loc or loc.kind != "settlement" or self.state.inventory.get(item_id, 0) < 1:
            return False
        if self.item_count(item_id) - 1 < self.reserved_item_count(item_id):
            self.log("Keep this item: an unfinished main tale needs it."); return False
        self.remove_item(item_id, 1); self.state.gold += self.price(item_id, False)
        self.log(f"Sold {self.index[item_id].name}.")
        return True

    def craft(self, recipe_id):
        recipe = self.index.get(recipe_id)
        if recipe_id not in {r.id for r in self.spec.crafting} or not self.alive(self.player):
            return False
        if recipe.required_skill_id and recipe.required_skill_id not in self.state.mastered_skills:
            return False
        if self.state.gold < recipe.gold_cost or any(self.state.inventory.get(eid, 0) < n for eid, n in recipe.ingredients.items()):
            self.log("Missing crafting materials."); return False
        if any(self.item_count(eid) - n < self.reserved_item_count(eid) for eid, n in recipe.ingredients.items()):
            self.log("An unfinished main tale needs these materials."); return False
        pack_after = sum(self.state.inventory.values()) - sum(recipe.ingredients.values()) + sum(recipe.outputs.values())
        if pack_after > self.rules.inventory_capacity:
            return False
        for eid, n in recipe.ingredients.items():
            self.remove_item(eid, n)
        self.state.gold -= recipe.gold_cost
        for eid, n in recipe.outputs.items():
            self.add_item(eid, n)
        self.state.crafted[recipe_id] = self.state.crafted.get(recipe_id, 0) + 1
        self.train("craft"); self.tick(); self.log(f"Crafted {recipe.name}.")
        return True

    def caravan(self, destination_id):
        loc = self.location_here(); dest = self.index.get(destination_id)
        if not loc or loc.kind != "settlement" or destination_id not in self.state.visited or dest.kind != "settlement" or self.state.gold < self.spec.economy.caravan_price:
            return False
        self.state.gold -= self.spec.economy.caravan_price
        self.state.return_stack.clear(); self.close_dialogue()
        self.player.map_id = dest.region_id; self.player.x, self.player.y = self.state.maps[dest.region_id].points[dest.id]
        for _ in range(5):
            self.tick(enemies=False)
        self.enter(dest.id); self.log(f"Caravan reached {dest.name}.")
        return True

    def travel_region(self, region_id):
        base = self.player.map_id
        if not self.alive(self.player) or base not in {r.id for r in self.spec.regions} or region_id not in self.index[base].neighbor_ids:
            return False
        self.player.map_id = region_id; self.player.x, self.player.y = self.current_map.entrance
        self._spawn_encounters(); self.tick(); return True

    def swear(self, faction_id):
        loc = self.location_here()
        if not loc or loc.faction_id != faction_id or faction_id not in {f.id for f in self.spec.factions}:
            return False
        if self.state.oath and self.state.oath != faction_id:
            self.state.standing[self.state.oath] = self.state.standing.get(self.state.oath, 0) - 5
        self.state.oath = faction_id; self.log(f"Swore to {self.index[faction_id].name}."); return True

    def spawn(self, enemy_id: str, map_id: str, count: int, table_id: str, generation: int):
        m = self.state.maps[map_id]
        definition = self.index[enemy_id]
        candidates = sorted(m.reachable())
        rng = random.Random(stable_seed(self.state.seed, table_id, generation, map_id, enemy_id))
        rng.shuffle(candidates)
        occupied = {(a.x, a.y) for a in self.state.actors.values() if a.map_id == map_id and self.alive(a)}
        safe_points = m.points.values() if map_id in {r.id for r in self.spec.regions} else [m.entrance]
        candidates = [xy for xy in candidates if xy not in occupied and all(abs(xy[0] - p[0]) + abs(xy[1] - p[1]) > 4 for p in safe_points)]
        if definition.role == "boss" and "boss" in m.points:
            boss = tuple(m.points["boss"])
            if boss in candidates:
                candidates.remove(boss); candidates.insert(0, boss)
        for i, xy in enumerate(candidates[:count]):
            aid = f"{table_id}:{generation}:{map_id}:{enemy_id}:{i}"
            if aid not in self.state.actors:
                self.state.actors[aid] = self._actor(definition, aid, map_id, *xy)

    def _spawn_encounters(self):
        for table in self.spec.encounters:
            key = table.location_id or table.region_id
            if not self.conditions(table.conditions):
                continue
            loc = self.index.get(table.location_id)
            if loc and loc.kind in ("dungeon", "ruin") and loc.depth > 1:
                keys = [key if floor == 0 else f"{key}:{floor}" for floor in range(loc.depth)]
            else:
                keys = [key]
            stamp = table.id + ":" + key
            exists = stamp in self.state.encounter_turns
            living = any(a.id.startswith(table.id + ":") and self.alive(a) for a in self.state.actors.values())
            if exists and (not table.respawn_turns or living or self.state.turn - self.state.encounter_turns[stamp] < table.respawn_turns):
                continue
            generation = self.state.encounter_generations.get(stamp, -1) + 1
            for map_id in keys:
                if map_id not in self.state.maps:
                    continue
                for enemy_id, count in sorted(table.enemy_counts.items()):
                    enemy = self.index[enemy_id]
                    if enemy.role == "boss" and map_id != keys[-1]:
                        continue
                    self.spawn(enemy_id, map_id, count, table.id, generation)
            self.state.encounter_turns[stamp] = self.state.turn
            self.state.encounter_generations[stamp] = generation

    def threats(self, actor: ActorState | None = None):
        actor = actor or self.player
        result = [a for a in self.state.actors.values() if a.map_id == actor.map_id and self.alive(a) and not a.friendly]
        return sorted(result, key=lambda a: (abs(a.x - actor.x) + abs(a.y - actor.y), a.id))

    def line_clear(self, a: ActorState, b: ActorState):
        if a.map_id != b.map_id:
            return False
        x, y = a.x, a.y; tx, ty = b.x, b.y
        dx, dy = abs(tx - x), abs(ty - y); sx, sy = (1 if x < tx else -1), (1 if y < ty else -1)
        error = dx - dy
        while (x, y) != (tx, ty):
            e = error * 2
            if e > -dy:
                error -= dy; x += sx
            if e < dx:
                error += dx; y += sy
            if (x, y) != (tx, ty) and not self.state.maps[a.map_id].walkable(x, y):
                return False
        return True

    def distance(self, a, b):
        return abs(a.x - b.x) + abs(a.y - b.y) if a.map_id == b.map_id else 100000

    def use_ability(self, ability_id: str, target_id: str | None = None, style: str = "normal") -> bool:
        if not self.alive(self.player) or ability_id not in self.known_abilities() or self.state.active_dialogue_id:
            return False
        if self.restrained():
            return True
        ability = self.index[ability_id]
        if self.player.cooldowns.get(ability_id, 0) > self.state.turn or any(self.player.resources.get(r, 0) < n for r, n in ability.cost.items()):
            self.log("Ability is cooling down or lacks resources."); return False
        if ability.target == "self":
            targets = [self.player]
        elif ability.target == "ally":
            targets = [a for a in self.state.actors.values() if a.friendly and self.distance(a, self.player) <= ability.range and self.alive(a)]
        else:
            candidates = [a for a in self.threats() if self.distance(a, self.player) <= ability.range and self.line_clear(self.player, a)]
            marked = target_id or self.state.target_id
            if ability.target == "all_enemies":
                targets = [a for a in candidates if self.distance(a, self.player) <= ability.radius or ability.radius == 0]
            elif marked:
                targets = [a for a in candidates if a.id == marked]
            else:
                targets = candidates[:1]
        if not targets:
            self.log("No target in reach."); return False
        rng = self.rng()
        for resource_id, cost in ability.cost.items():
            self.player.resources[resource_id] -= cost
        self.player.cooldowns[ability_id] = self.state.turn + ability.cooldown + 1
        multiplier = 100
        accuracy = ability.accuracy
        if style == "heavy":
            multiplier = 170; accuracy = min(75, accuracy); self.player.winded = True
        elif style == "quick":
            multiplier = 65
        for target in targets:
            if rng.randrange(100) >= accuracy:
                self.log(f"{ability.name} misses."); continue
            if style == "quick" and target.telegraph:
                target.telegraph = False; self.log("A quick action spoils the incoming heavy.")
            for effect in ability.effects:
                self.apply_effect(self.player, target, effect, ability, multiplier, rng)
                if not self.alive(target):
                    break
        self.train("combat")
        self.tick(soft=style == "quick")
        return True

    def damage(self, attacker: ActorState, target: ActorState, amount: int, damage_type: str) -> int:
        definition = self.index[target.definition_id]
        amount = max(1, amount - self.stat(target, self.rules.armor_stat_id))
        resist = definition.resistances.get(damage_type, 0)
        vulnerable = definition.vulnerabilities.get(damage_type, 0)
        if target is self.player:
            resist = min(100, resist + sum(self.index[i].resistances.get(damage_type, 0) for i in self.state.equipment.values()))
            resist = min(100, resist + sum(p.resistances.get(damage_type, 0) for p in self.spec.player.passives if p.trigger == "always"))
        amount = amount * (100 + vulnerable) // 100 * (100 - resist) // 100
        if target.guard:
            amount = max(1, amount // 4) if amount else 0
            target.guard = False
        if target.winded:
            amount = amount * 150 // 100; target.winded = False
        absorbed = min(target.shield, amount); target.shield -= absorbed; amount -= absorbed
        target.resources[self.health_id] = max(0, target.resources[self.health_id] - amount)
        self.log(f"{self.index[attacker.definition_id].name} deals {amount} {self.index[damage_type].name} to {definition.name}.")
        if amount:
            target.telegraph = False
        if not self.alive(target) and target is not self.player:
            self.defeat(target)
        if not self.alive(self.player):
            self.log("You have fallen. R returns you to the hearth at a cost.")
        return amount

    def apply_effect(self, attacker, target, effect: Effect, ability: Ability | None = None, multiplier: int = 100, rng: random.Random | None = None):
        rng = rng or self.rng()
        if effect.kind == "damage":
            raw = effect.amount + (ability.power_scale * self.stat(attacker, self.rules.power_stat_id) if ability else 0)
            self.damage(attacker, target, raw * multiplier // 100, effect.damage_type)
        elif effect.kind == "heal":
            rid = effect.resource_id
            target.resources[rid] = min(target.caps.get(rid, 0), target.resources.get(rid, 0) + effect.amount)
        elif effect.kind == "shield":
            target.shield += effect.amount
        elif effect.kind == "status":
            target.statuses[effect.status_id] = max(target.statuses.get(effect.status_id, 0), effect.duration)
        elif effect.kind == "cleanse":
            if effect.status_id:
                target.statuses.pop(effect.status_id, None)
            else:
                target.statuses.clear()
        elif effect.kind in ("push", "teleport"):
            actor = target if effect.kind == "push" else attacker
            for _ in range(effect.amount):
                if effect.kind == "push":
                    dx, dy = target.x - attacker.x, target.y - attacker.y
                    dx, dy = (1 if dx > 0 else -1 if dx < 0 else 0, 0) if abs(dx) >= abs(dy) else (0, 1 if dy > 0 else -1)
                else:
                    dx, dy = rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
                if self.actor_walkable(actor, actor.x + dx, actor.y + dy):
                    actor.x += dx; actor.y += dy
        elif effect.kind == "summon":
            before = set(self.state.actors)
            self.spawn(effect.enemy_id, attacker.map_id, 1, "summon", self.state.rng_counter)
            for aid in set(self.state.actors) - before:
                ally = self.state.actors[aid]; ally.friendly = attacker is self.player or attacker.friendly; ally.ally_until = self.state.turn + effect.duration
                candidates = sorted(self.current_map.reachable(), key=lambda xy: (abs(xy[0] - attacker.x) + abs(xy[1] - attacker.y), xy))
                ally.x, ally.y = candidates[min(1, len(candidates) - 1)]
        elif effect.kind == "reveal":
            for loc in self.spec.locations:
                if loc.region_id == self.player.map_id:
                    self.log(f"Sensed {loc.name} at {self.current_map.points[loc.id]}.")
        elif effect.kind == "negotiate":
            difficulty = self.index[target.definition_id].negotiation_difficulty
            if self.stat(attacker, self.rules.influence_stat_id) + effect.amount + rng.randrange(6) >= difficulty:
                self.log(f"{self.index[target.definition_id].name} accepts your terms.")
                self.defeat(target, negotiated=True)
            else:
                self.log("The offer is refused.")

    def defeat(self, target, negotiated=False):
        if target.defeated:
            return
        target.defeated = True
        if self.state.target_id == target.id: self.state.target_id = None
        if target.friendly:
            return
        definition = self.index[target.definition_id]
        self.state.kills[definition.id] = self.state.kills.get(definition.id, 0) + 1
        self.state.gold += definition.gold
        self.gain_xp(definition.xp)
        for eid, n in sorted(definition.loot.items()):
            if n:
                self.add_item(eid, n, at=target)
        if definition.faction_id:
            self.state.standing[definition.faction_id] = self.state.standing.get(definition.faction_id, 0) + (1 if negotiated else -2)
            for fid, relation in self.index[definition.faction_id].relationships.items():
                self.state.standing[fid] = self.state.standing.get(fid, 0) + (-1 if relation > 0 else 1)
        self.player.winded = False
        self.passive_event("on_negotiate" if negotiated else "on_kill")
        self.log(f"Resolved {definition.name}. +{definition.xp} experience.")

    def defend(self):
        if not self.alive(self.player):
            return False
        if self.restrained():
            return True
        self.player.guard = True; self.log("You prepare to turn the next blow."); self.tick(); return True

    def use_item(self, item_id):
        if not self.alive(self.player) or self.state.inventory.get(item_id, 0) < 1:
            return False
        if self.restrained():
            return True
        item = self.index[item_id]
        if item.kind != "consumable":
            return self.equip(item_id)
        if self.item_count(item_id) - 1 < self.reserved_item_count(item_id):
            self.log("An unfinished main tale needs this item."); return False
        if any(e.kind in ("damage", "status", "push", "negotiate") for e in item.effects):
            targets = self.threats()
            target = next((a for a in targets if a.id == self.state.target_id), targets[0] if targets else None)
            if not target or self.distance(self.player, target) > 4 or not self.line_clear(self.player, target):
                return False
        else:
            target = self.player
        self.remove_item(item_id, 1)
        for effect in item.effects:
            self.apply_effect(self.player, target, effect)
        self.tick(); return True

    def flee(self):
        if not self.alive(self.player):
            return False
        if self.restrained():
            return True
        threats = self.threats()
        if not threats:
            return False
        chance = min(90, 55 + self.stat(self.player, self.rules.speed_stat_id) * 3)
        if self.rng().randrange(100) < chance:
            for _ in range(3):
                candidates = [(self.player.x + dx, self.player.y + dy) for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]
                              if self.player_walkable(self.player.map_id, self.player.x + dx, self.player.y + dy)]
                if candidates:
                    self.player.x, self.player.y = max(candidates, key=lambda xy: (min(abs(xy[0] - a.x) + abs(xy[1] - a.y) for a in threats), xy))
            self.player.winded = False; self.log("Disengaged into clearer ground."); self.tick(enemies=False)
        else:
            self.log("The retreat is cut off."); self.tick()
        return True

    def respawn(self):
        if self.alive(self.player):
            return False
        loc = self.index[self.spec.player.starting_location_id]
        self.state.gold -= self.state.gold * self.rules.death_gold_percent // 100
        self.player.resources = dict(self.player.caps); self.player.statuses.clear()
        self.player.defeated = False; self.player.shield = 0; self.player.winded = self.player.guard = False
        self.player.map_id = loc.region_id; self.player.x, self.player.y = self.state.maps[loc.region_id].points[loc.id]
        self.state.return_stack.clear(); self.state.target_id = None; self.close_dialogue()
        self.log("You rise at the hearth. Your deeds remain."); return True

    def step_toward(self, actor, target, retreat=False):
        m = self.state.maps[actor.map_id]
        occupied = {(a.x, a.y) for a in [self.player, *self.state.actors.values()] if a.id != actor.id and a.map_id == actor.map_id and self.alive(a)}
        choices = [(actor.x + dx, actor.y + dy) for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]
                   if self.actor_walkable(actor, actor.x + dx, actor.y + dy) and (actor.x + dx, actor.y + dy) not in occupied]
        if choices:
            key = lambda xy: (abs(xy[0] - target.x) + abs(xy[1] - target.y), xy)
            actor.x, actor.y = (max if retreat else min)(choices, key=key)

    def _enemy_turn(self, actor, soft=False):
        definition = self.index[actor.definition_id]
        if definition.behavior == "passive" or any(self.index[s].skip_turn for s in actor.statuses):
            return
        if actor.friendly:
            targets = self.threats(actor)
            target = targets[0] if targets else None
        else:
            allies = [a for a in self.state.actors.values() if a.friendly and self.alive(a) and a.map_id == actor.map_id]
            target = min([self.player, *allies], key=lambda a: (self.distance(actor, a), a.id))
        if not target or self.distance(actor, target) > 7:
            return
        if actor.resources[self.health_id] <= actor.caps[self.health_id] // 3 and isinstance(definition, EnemyArchetype) and definition.role == "boss" and not actor.enraged:
            actor.enraged = True; actor.abilities = list(dict.fromkeys(actor.abilities + definition.phase_ability_ids))
            self.log(f"{definition.name} changes tactics and enrages!")
        usable = [self.index[aid] for aid in actor.abilities if actor.cooldowns.get(aid, 0) <= self.state.turn
                  and all(actor.resources.get(r, 0) >= n for r, n in self.index[aid].cost.items())]
        if definition.behavior == "support":
            hurt = [a for a in self.state.actors.values() if a.map_id == actor.map_id and a.friendly == actor.friendly and self.alive(a)
                    and a.resources[self.health_id] < a.caps[self.health_id] // 2]
            heal = next((a for a in usable if a.target == "ally" and any(e.kind == "heal" for e in a.effects)), None)
            if hurt and heal:
                target = min(hurt, key=lambda a: a.resources[self.health_id])
                if self.distance(actor, target) <= heal.range:
                    for r, n in heal.cost.items(): actor.resources[r] -= n
                    for effect in heal.effects: self.apply_effect(actor, target, effect, heal)
                    actor.cooldowns[heal.id] = self.state.turn + heal.cooldown + 1
                    return
        attack = next((a for a in sorted(usable, key=lambda a: (-a.range, a.id)) if a.target in ("enemy", "all_enemies") and self.distance(actor, target) <= a.range and self.line_clear(actor, target)), None)
        if definition.behavior == "ranged" and self.distance(actor, target) <= 1:
            self.step_toward(actor, target, True); return
        if not attack:
            self.step_toward(actor, target); return
        if not actor.telegraph and self.state.turn % 3 == 0:
            actor.telegraph = True; self.log(f"{definition.name} prepares a heavy reply. Guard or disrupt it!"); return
        multiplier = (170 if actor.telegraph else 100) + (30 if actor.enraged else 0)
        actor.telegraph = False
        if soft: multiplier = multiplier * 70 // 100
        for r, n in attack.cost.items(): actor.resources[r] -= n
        rng = self.rng()
        if rng.randrange(100) < attack.accuracy:
            for effect in attack.effects:
                self.apply_effect(actor, target, effect, attack, multiplier, rng)
        actor.cooldowns[attack.id] = self.state.turn + attack.cooldown + 1

    def tick(self, *, enemies=True, soft=False):
        self.state.turn += 1
        for actor in [self.player, *sorted(self.state.actors.values(), key=lambda a: a.id)]:
            if not self.alive(actor):
                continue
            for r in self.spec.resources:
                if r.id in actor.resources:
                    actor.resources[r.id] = min(actor.caps[r.id], actor.resources[r.id] + r.regen)
            if actor is self.player:
                self.passive_event("turn")
            if actor.ally_until and actor.ally_until <= self.state.turn:
                actor.defeated = True; continue
            for sid in list(actor.statuses):
                status = self.index[sid]
                if status.tick_damage:
                    self.damage(self.player if actor is not self.player else actor, actor, status.tick_damage, status.damage_type)
            # A one-turn restraint must still cover this actor's reply. Expire
            # durations after the action, rather than removing it beforehand.
            if enemies and actor is not self.player and actor.map_id == self.player.map_id and self.alive(actor) and self.alive(self.player):
                self._enemy_turn(actor, soft)
            for sid in list(actor.statuses):
                actor.statuses[sid] -= 1
                if actor.statuses[sid] <= 0:
                    del actor.statuses[sid]
        for qid in self.active_quests():
            quest = self.index[qid]
            if quest.deadline_turns and self.state.turn - self.state.quest_start_turns[qid] > quest.deadline_turns:
                self.state.quests_failed.append(qid); self.log(f"The deadline passed: {quest.name}.")
        for event in self.spec.world_events:
            previous = self.state.event_turns.get(event.id)
            if previous is not None and (event.once or self.state.turn - previous < event.cooldown_turns):
                continue
            if self.conditions(event.conditions):
                self.state.event_turns[event.id] = self.state.turn
                self.grant_actions(event.actions); self.state.annals.append(f"Day {self.day}: {event.name} — {event.description}")
                self.log(f"{event.name}: {event.description}")
        self._spawn_encounters()

    def _validate_save(self):
        s = self.state
        if s.turn < 0 or s.rng_counter < 0 or s.gold < 0 or s.level < 1:
            raise ValueError("Invalid save counters")
        expected_maps = set(build_maps(self.spec))
        if set(s.maps) != expected_maps:
            raise ValueError("Save map IDs do not match this realm")
        for mid, m in s.maps.items():
            if m.id != mid or not m.grid or not m.grid[0] or any(len(row) != len(m.grid[0]) for row in m.grid):
                raise ValueError("Invalid saved map")
            if not m.walkable(*m.entrance):
                raise ValueError("Invalid saved map entrance")
        actor_definitions = {self.spec.player.id, *(a.id for a in self.spec.enemies), *(a.id for a in self.spec.npcs)}
        stats = {x.id for x in self.spec.stats}; resources = {x.id for x in self.spec.resources}
        statuses = {x.id for x in self.spec.status_effects}; abilities = {x.id for x in self.spec.abilities}
        for actor in [s.player, *s.actors.values()]:
            valid_position = actor.map_id in s.maps and self.actor_walkable(actor, actor.x, actor.y)
            valid_definition = actor.definition_id == self.spec.player.id if actor is s.player else actor.definition_id in actor_definitions - {self.spec.player.id}
            if not valid_definition or not valid_position or (actor is not s.player and actor.definition_id in {n.id for n in self.spec.npcs} and not actor.friendly):
                raise ValueError("Invalid saved actor location/definition")
            if actor is s.player and actor.definition_id != self.spec.player.id:
                raise ValueError("Invalid player definition")
            if (set(actor.resources) != set(actor.caps) or not set(actor.resources) <= resources
                or self.health_id not in actor.resources or any(value <= 0 for value in actor.caps.values())
                or any(value < 0 or value > actor.caps[key] for key, value in actor.resources.items())):
                raise ValueError("Invalid saved resources")
            if not set(actor.stats) <= stats or not set(actor.statuses) <= statuses:
                raise ValueError("Invalid saved stats/statuses")
            if not set(actor.abilities) <= abilities or not set(actor.cooldowns) <= abilities:
                raise ValueError("Invalid saved abilities")
        if any(key != actor.id for key, actor in s.actors.items()):
            raise ValueError("Invalid saved actor IDs")
        if any(eid not in {i.id for i in self.spec.items} or n <= 0 for eid, n in s.inventory.items()):
            raise ValueError("Invalid saved inventory")
        for drop in s.pending_loot.values():
            if drop.map_id not in s.maps or not self.player_walkable(drop.map_id, drop.x, drop.y) or any(eid not in {i.id for i in self.spec.items} or n <= 0 for eid, n in drop.items.items()):
                raise ValueError("Invalid saved pending loot")
        if not set(s.companions) <= {n.id for n in self.spec.npcs} or not set(s.companions.values()) <= {loc.id for loc in self.spec.locations}:
            raise ValueError("Invalid saved companion references")
        for npc_id, xy in s.npc_positions.items():
            if npc_id not in {n.id for n in self.spec.npcs} or len(xy) != 2 or not s.maps[self.npc_map_id(self.index[npc_id])].walkable(*xy):
                raise ValueError("Invalid saved NPC position")
        if any(slot not in self.spec.player.equipment_slots or eid not in self.index or self.index[eid].slot_id != slot for slot, eid in s.equipment.items()):
            raise ValueError("Invalid saved equipment")
        quests = {q.id for q in self.spec.quests}
        if not set(s.quests_known + s.quests_done + s.quests_failed) <= quests:
            raise ValueError("Invalid saved quests")
        for spot in s.return_stack:
            if (set(spot) != {"map_id", "x", "y"} or spot["map_id"] not in s.maps
                or not isinstance(spot["x"], int) or not isinstance(spot["y"], int)
                or not s.maps[spot["map_id"]].walkable(spot["x"], spot["y"])):
                raise ValueError("Invalid saved return position")
        if s.active_dialogue_id:
            if s.active_dialogue_id not in {d.id for d in self.spec.dialogues} or s.active_npc_id not in {n.id for n in self.spec.npcs}:
                raise ValueError("Invalid saved dialogue")
            if s.active_dialogue_node not in {n.id for n in self.index[s.active_dialogue_id].nodes}:
                raise ValueError("Invalid saved dialogue node")

    def save(self, path: str | Path):
        self._validate_save()
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=f".{destination.name}-", dir=destination.parent)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(canonical(self.state.model_dump(mode="json"))); f.flush(); os.fsync(f.fileno())
            os.replace(name, destination)
        finally:
            if os.path.exists(name): os.unlink(name)

    @classmethod
    def load(cls, package: RealmPackage, path: str | Path):
        return cls(package, SaveGame.model_validate_json(Path(path).read_bytes()))
