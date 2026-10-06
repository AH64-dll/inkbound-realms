"""Cross-object and mechanical validation shared by compiler and package loader."""
from __future__ import annotations

from dataclasses import dataclass

from inkbound.realm.models import Action, Condition, Effect, RealmSpec
from inkbound.runtime.maps import build_maps


@dataclass(frozen=True)
class Issue:
    code: str
    path: str
    message: str
    severity: str = "error"


class InvalidRealm(ValueError):
    def __init__(self, issues: list[Issue]):
        self.issues = issues
        super().__init__("\n".join(f"{i.code} {i.path}: {i.message}" for i in issues if i.severity == "error"))


def validate_realm(spec: RealmSpec, *, check_maps: bool = True) -> list[Issue]:
    issues: list[Issue] = []

    def fail(code: str, path: str, message: str, severity: str = "error"):
        issues.append(Issue(code, path, message, severity))

    seen: set[str] = set()
    for e in spec.entities():
        if e.id in seen:
            fail("duplicate_id", e.id, "IDs must be globally unique")
        seen.add(e.id)
    if any(i.code == "duplicate_id" for i in issues):
        # A colliding typed object cannot be safely used by later cross-checks.
        return issues
    groups = {field: {e.id for e in getattr(spec, field)} for field in (
        "stats", "resources", "damage_types", "equipment_slots", "abilities", "status_effects", "skills", "progression",
        "classes", "species", "factions", "regions", "locations", "npcs", "enemies", "quests", "items", "crafting", "dialogues", "assets")}
    index = spec.index()

    def ref(value, group: str, path: str, optional: bool = False):
        if value is None and optional:
            return
        if value not in groups[group]:
            fail("invalid_reference", path, f"{value!r} is not a {group} ID")

    def refs(values, group, path):
        for v in values:
            ref(v, group, path)

    def condition(c: Condition, path: str):
        group = {"quest_done": "quests", "quest_active": "quests", "item": "items", "standing": "factions",
                 "visited": "locations", "kills": "enemies"}.get(c.kind)
        if group:
            ref(c.target, group, path)
        elif c.kind == "flag" and not c.target:
            fail("invalid_condition", path, "A flag needs a target ID")
        elif c.kind in ("level", "turn") and c.target:
            fail("invalid_condition", path, "Level/turn conditions have no target")

    def action(a: Action, path: str):
        group = {"grant_item": "items", "standing": "factions", "unlock": "locations", "heal": "resources",
                 "spawn": "enemies", "start_quest": "quests"}.get(a.kind)
        if group:
            ref(a.target, group, path)
        if a.kind == "flag" and not a.target:
            fail("invalid_action", path, "A flag needs a target ID")
        if a.kind in ("grant_item", "xp", "heal", "spawn") and a.amount <= 0:
            fail("invalid_action", path, "This action needs a positive amount")

    def effect(e: Effect, path: str):
        for v, group in [(e.damage_type, "damage_types"), (e.resource_id, "resources"),
                         (e.status_id, "status_effects"), (e.enemy_id, "enemies")]:
            if v is not None:
                ref(v, group, path)
        required = {"damage": e.damage_type, "heal": e.resource_id, "status": e.status_id, "summon": e.enemy_id}
        if e.kind in required and required[e.kind] is None:
            fail("unsupported_effect", path, f"{e.kind} is missing its required reference")
        if e.kind in ("damage", "heal", "shield", "push", "teleport", "negotiate") and e.amount <= 0:
            fail("ineffective_ability", path, f"{e.kind} has no meaningful magnitude")

    rules = spec.world_rules
    for value, group in [(rules.health_resource_id, "resources"), (rules.power_stat_id, "stats"),
                         (rules.armor_stat_id, "stats"), (rules.speed_stat_id, "stats"),
                         (rules.influence_stat_id, "stats"), (rules.default_damage_type_id, "damage_types"),
                         (rules.default_ability_id, "abilities")]:
        ref(value, group, "world_rules")
    health = index.get(rules.health_resource_id) if rules.health_resource_id in groups["resources"] else None
    if health and health.role != "health":
        fail("invalid_health", "world_rules", "Health resource must carry the health role")

    p = spec.player
    refs(p.stats, "stats", "player.stats"); refs(p.resources, "resources", "player.resources")
    refs(p.equipment_slots, "equipment_slots", "player.equipment_slots")
    refs(p.ability_ids + p.interaction_ability_ids, "abilities", "player.abilities")
    refs(p.starting_items, "items", "player.starting_items")
    refs(p.resistances.keys() | p.vulnerabilities.keys(), "damage_types", "player.affinity")
    ref(p.progression_id, "progression", "player.progression"); ref(p.starting_location_id, "locations", "player.start")
    ref(p.species_id, "species", "player.species", True); ref(p.class_id, "classes", "player.class", True)
    if rules.health_resource_id not in p.resources:
        fail("invalid_player", "player.resources", "Player has no health")
    if rules.default_ability_id not in p.ability_ids:
        fail("invalid_player", "player.abilities", "Player must know the default attack")
    if not set(p.special_mechanics) <= set(rules.supported_mechanics):
        fail("unsupported_mechanics", "player.special_mechanics", "Engine cannot implement requested mechanics")
    if len({x.id for x in p.passives}) != len(p.passives):
        fail("duplicate_passive", p.id, "Passive IDs must be unique within the player")
    for passive in p.passives:
        refs(passive.stat_mods, "stats", passive.id)
        refs(passive.resource_gain, "resources", passive.id)
        refs(passive.resistances, "damage_types", passive.id)
        if not passive.stat_mods and not passive.resistances and not any(passive.resource_gain.values()):
            fail("ineffective_passive", passive.id, "Passive needs an executable effect")
        if passive.trigger == "always" and passive.resource_gain or passive.trigger != "always" and (passive.stat_mods or passive.resistances):
            fail("invalid_passive", passive.id, "Always supports stat/affinity modifiers; event triggers support resource gains")
        if any(rid not in p.resources for rid in passive.resource_gain) or any(not 0 <= n <= 100 for n in passive.resistances.values()):
            fail("invalid_passive", passive.id, "Resource gain or resistance is incompatible with the player")

    for actor in [p, *spec.enemies]:
        refs(actor.stats, "stats", actor.id); refs(actor.resources, "resources", actor.id)
        refs(actor.ability_ids, "abilities", actor.id)
        refs(actor.resistances.keys() | actor.vulnerabilities.keys(), "damage_types", actor.id)
        for key, value in actor.stats.items():
            stat = index.get(key) if key in groups["stats"] else None
            if stat and not stat.minimum <= value <= stat.maximum:
                fail("invalid_stat", actor.id, f"{key} outside allowed range")
        for key, value in actor.resistances.items():
            if not 0 <= value <= 100:
                fail("invalid_resistance", actor.id, f"{key}: use 0..100 percent")
        for key, value in actor.vulnerabilities.items():
            if not 0 <= value <= 200:
                fail("invalid_vulnerability", actor.id, f"{key}: use 0..200 percent")
        actor_abilities = list(actor.ability_ids)
        if actor is p:
            actor_abilities += p.interaction_ability_ids
            if p.class_id in groups["classes"]: actor_abilities += index[p.class_id].ability_ids
        for aid in actor_abilities:
            ability = index.get(aid)
            if aid in groups["abilities"] and any(rid not in actor.resources or cost > actor.resources[rid] for rid, cost in ability.cost.items()):
                fail("unsupported_ability", actor.id, f"Cannot pay the cost of {aid}")

    for stat in spec.stats:
        if stat.minimum > stat.maximum:
            fail("invalid_stat", stat.id, "Minimum exceeds maximum")
    for a in spec.abilities:
        refs(a.cost, "resources", a.id)
        for e in a.effects:
            effect(e, a.id)
        if a.target == "self" and any(e.kind in ("damage", "negotiate") for e in a.effects):
            fail("invalid_target", a.id, "Self damage/negotiation is not supported")
        if a.target == "ally" and any(e.kind == "negotiate" for e in a.effects):
            fail("invalid_target", a.id, "Negotiation requires a hostile target")
    for status in spec.status_effects:
        refs(status.stat_mods, "stats", status.id)
        if status.tick_damage:
            ref(status.damage_type, "damage_types", status.id)
    for item in spec.items:
        ref(item.slot_id, "equipment_slots", item.id, item.kind not in ("equipment", "artifact"))
        refs(item.stat_mods, "stats", item.id); refs(item.resistances, "damage_types", item.id)
        refs(item.ability_ids, "abilities", item.id)
        if any(not 0 <= x <= 100 for x in item.resistances.values()):
            fail("invalid_resistance", item.id, "Equipment resistance must be 0..100")
        for e in item.effects:
            effect(e, item.id)
        if item.kind == "consumable" and not item.effects:
            fail("ineffective_item", item.id, "Consumable has no effects")
    for key in p.starting_items:
        item = index.get(key) if key in groups["items"] else None
        if item and item.slot_id and item.slot_id not in p.equipment_slots:
            fail("invalid_equipment", key, "Starting equipment has no compatible player slot")
    for prog in spec.progression:
        refs(prog.stat_growth, "stats", prog.id); refs(prog.resource_growth, "resources", prog.id)
        refs(prog.skill_ids, "skills", prog.id)
        for level, abilities in prog.unlocks.items():
            if not level.isdigit() or not 2 <= int(level) <= 100:
                fail("broken_progression", prog.id, "Unlock levels must be integers 2..100")
            refs(abilities, "abilities", prog.id)
    for skill in spec.skills:
        refs(skill.ability_ids, "abilities", skill.id); refs(skill.stat_mods, "stats", skill.id)
        refs(skill.prerequisites, "skills", skill.id)
    for cls in spec.classes:
        refs(cls.ability_ids, "abilities", cls.id); refs(cls.stat_mods, "stats", cls.id)
        ref(cls.progression_id, "progression", cls.id)
    for species in spec.species:
        refs(species.stat_mods, "stats", species.id)
    for f in spec.factions:
        refs(f.relationships, "factions", f.id); ref(f.home_location_id, "locations", f.id)
    for region in spec.regions:
        refs(region.faction_ids, "factions", region.id)
        refs(region.neighbor_ids, "regions", region.id)
    positions = set()
    for loc in spec.locations:
        position = (loc.region_id, loc.x, loc.y)
        if position in positions:
            fail("overlapping_locations", loc.id, "Two locations occupy the same region tile")
        positions.add(position)
        ref(loc.region_id, "regions", loc.id); ref(loc.faction_id, "factions", loc.id, True)
        refs(loc.market_items, "items", loc.id)
        for c in loc.locked_by:
            condition(c, loc.id)
        for a in loc.entry_actions:
            action(a, loc.id)
    for npc in spec.npcs:
        ref(npc.location_id, "locations", npc.id); ref(npc.faction_id, "factions", npc.id, True)
        ref(npc.dialogue_id, "dialogues", npc.id); refs(npc.relationships, "npcs", npc.id)
        refs(npc.stats, "stats", npc.id); refs(npc.resources, "resources", npc.id)
        refs(npc.ability_ids, "abilities", npc.id)
        refs(npc.resistances.keys() | npc.vulnerabilities.keys(), "damage_types", npc.id)
        if npc.resources and rules.health_resource_id not in npc.resources:
            fail("invalid_npc", npc.id, "Companion resources require health")
    for enemy in spec.enemies:
        ref(enemy.faction_id, "factions", enemy.id, True); refs(enemy.loot, "items", enemy.id)
        refs(enemy.phase_ability_ids, "abilities", enemy.id)
        if rules.health_resource_id not in enemy.resources:
            fail("invalid_enemy", enemy.id, "Enemy has no health")

    for dialogue in spec.dialogues:
        nodes = {n.id for n in dialogue.nodes}
        if len(nodes) != len(dialogue.nodes) or dialogue.start_node_id not in nodes:
            fail("malformed_dialogue", dialogue.id, "Duplicate nodes or missing start")
        reachable = {dialogue.start_node_id}
        for _ in dialogue.nodes:
            for node in dialogue.nodes:
                if node.id in reachable:
                    reachable.update(c.next_node_id for c in node.choices if c.next_node_id)
        if not nodes <= reachable:
            fail("malformed_dialogue", dialogue.id, "Unreachable dialogue nodes")
        for node in dialogue.nodes:
            ids = [c.id for c in node.choices]
            if len(set(ids)) != len(ids):
                fail("malformed_dialogue", dialogue.id, "Duplicate choice IDs")
            for c in node.choices:
                if c.next_node_id and c.next_node_id not in nodes:
                    fail("malformed_dialogue", dialogue.id, "Choice links to nonexistent node")
                for cond in c.conditions:
                    condition(cond, dialogue.id)
                for a in c.actions:
                    action(a, dialogue.id)
                # Repeated conversation is not an infinite-money/inventory faucet.
                if c.actions and not any(cond.kind == "flag" and cond.negate for cond in c.conditions):
                    fail("repeatable_dialogue_reward", dialogue.id, "Action choices require a one-shot flag condition")
                guards = {cond.target for cond in c.conditions if cond.kind == "flag" and cond.negate}
                if c.actions and not any(a.kind == "flag" and a.target in guards and a.amount > 0 for a in c.actions):
                    fail("repeatable_dialogue_reward", dialogue.id, "Choice must set its own one-shot flag")

    for recipe in spec.crafting:
        refs(recipe.ingredients, "items", recipe.id); refs(recipe.outputs, "items", recipe.id)
        ref(recipe.required_skill_id, "skills", recipe.id, True)
        cost = recipe.gold_cost + sum(index[k].price * v for k, v in recipe.ingredients.items() if k in groups["items"])
        resale = sum(index[k].price * v * spec.economy.sell_percent // 100 for k, v in recipe.outputs.items() if k in groups["items"])
        if resale > cost:
            fail("impossible_economy", recipe.id, "Crafting creates unbounded resale profit")
    for table in spec.encounters:
        ref(table.region_id, "regions", table.id); ref(table.location_id, "locations", table.id, True)
        refs(table.enemy_counts, "enemies", table.id)
        if table.location_id in groups["locations"] and index[table.location_id].region_id != table.region_id:
            fail("invalid_spawn", table.id, "Encounter region does not contain its location")
        for c in table.conditions:
            condition(c, table.id)
    for event in spec.world_events:
        for c in event.conditions:
            condition(c, event.id)
        for a in event.actions:
            action(a, event.id)
    for entry in spec.history:
        for eid in entry.entity_ids:
            if eid not in index:
                fail("invalid_reference", "history", f"Missing {eid}")

    # Dependency cycles apply to skill trees and quest arcs alike.
    for objects, code in [(spec.quests, "circular_quests"), (spec.skills, "circular_skills")]:
        remaining = {o.id: set(o.prerequisites) for o in objects}
        done: set[str] = set()
        while remaining:
            ready = {k for k, parents in remaining.items() if parents <= done}
            if not ready:
                fail(code, ",".join(sorted(remaining)), "Dependency cycle or missing prerequisites")
                break
            done.update(ready)
            remaining = {k: v for k, v in remaining.items() if k not in ready}

    available_items = set(p.starting_items)
    available_items.update(k for loc in spec.locations for k in loc.market_items)
    available_items.update(k for enemy in spec.enemies for k in enemy.loot)
    source_actions = [a for q in spec.quests for a in q.reward_actions]
    source_actions.extend(a for loc in spec.locations for a in loc.entry_actions)
    source_actions.extend(a for event in spec.world_events for a in event.actions)
    source_actions.extend(a for dialogue in spec.dialogues for node in dialogue.nodes for choice in node.choices for a in choice.actions)
    available_items.update(a.target for a in source_actions if a.kind == "grant_item")
    for _ in spec.crafting:
        for recipe in spec.crafting:
            if set(recipe.ingredients) <= available_items:
                available_items.update(recipe.outputs)
    spawn_counts = {eid: sum(t.enemy_counts.get(eid, 0) for t in spec.encounters) for eid in groups["enemies"]}
    for a in source_actions:
        if a.kind == "spawn" and a.target in spawn_counts:
            spawn_counts[a.target] += a.amount
    # Generous global currency ceiling: reject demands exceeding even every
    # finite reward and sale. This is a necessary bound, not an economy solver.
    currency_ceiling = spec.economy.starting_gold + sum(a.amount for a in source_actions if a.kind == "gold")
    currency_ceiling += sum(index[eid].gold * count for eid, count in spawn_counts.items())
    currency_ceiling += sum(index[iid].price * n for iid, n in p.starting_items.items() if iid in groups["items"])
    currency_ceiling += sum(index[iid].price * n * spawn_counts[enemy.id] for enemy in spec.enemies for iid, n in enemy.loot.items() if iid in groups["items"])
    currency_ceiling += sum(index[a.target].price * a.amount for a in source_actions if a.kind == "grant_item" and a.target in groups["items"])
    renewable_currency = any(t.respawn_turns for t in spec.encounters) or any(not e.once and any(a.kind in ("gold", "grant_item", "spawn") for a in e.actions) for e in spec.world_events)
    for quest in spec.quests:
        ref(quest.giver_id, "npcs", quest.id); refs(quest.prerequisites, "quests", quest.id)
        for obj in quest.objectives:
            group = {"visit": "locations", "kill": "enemies", "talk": "npcs", "collect": "items", "craft": "crafting",
                     "pay": "locations", "escort": "npcs", "choice": "dialogues"}[obj.kind]
            ref(obj.target_id, group, quest.id)
            ref(obj.destination_id, "locations", quest.id, obj.kind != "escort")
            if obj.kind in ("visit", "talk", "escort", "choice") and obj.count != 1:
                fail("impossible_objective", quest.id, "This objective is a unique deed and its count must be one")
            if obj.kind == "collect" and obj.target_id not in available_items:
                fail("impossible_objective", quest.id, "Required item has no source")
            if obj.kind == "kill" and spawn_counts.get(obj.target_id, 0) < obj.count:
                if not any(t.respawn_turns and obj.target_id in t.enemy_counts for t in spec.encounters) and not any(not e.once and any(a.kind == "spawn" and a.target == obj.target_id for a in e.actions) for e in spec.world_events):
                    fail("impossible_objective", quest.id, "Not enough target enemies can spawn")
        if not renewable_currency and sum(o.count for o in quest.objectives if o.kind == "pay") > currency_ceiling:
            fail("impossible_economy", quest.id, "Required payment exceeds all finite currency and sale sources")
        for a in quest.reward_actions:
            action(a, quest.id)

    # Fixed point proves that entry locks and resource sources are not behind
    # the quest that requires them. Source declarations alone are insufficient.
    accessible = {loc.id for loc in spec.locations if not loc.locked_by}
    completable: set[str] = set()
    start = index.get(p.starting_location_id) if p.starting_location_id in groups["locations"] else None
    if start and start.locked_by:
        fail("inaccessible_area", p.starting_location_id, "Starting location is locked")
    reachable_regions = {start.region_id} if start else set()
    for _ in spec.regions:
        for region in spec.regions:
            if region.id in reachable_regions:
                reachable_regions.update(region.neighbor_ids)
    for region in spec.regions:
        if region.id not in reachable_regions:
            fail("inaccessible_area", region.id, "Region has no route from the starting region")
    accessible = {lid for lid in accessible if index[lid].region_id in reachable_regions}
    possible_flags: set[str] = set()
    possible_standing: dict[str, int] = {}
    possible_items = set(p.starting_items)
    possible_kills: set[str] = set()
    possible_level = 1

    def can_condition(c):
        if c.negate:
            # A negative initial condition can be met before the corresponding deed.
            return c.kind in ("flag", "quest_done", "quest_active", "visited", "kills", "item")
        if c.kind == "quest_done":
            return c.target in completable
        if c.kind == "quest_active":
            quest = index.get(c.target)
            if c.target not in groups["quests"]: return False
            giver = index.get(quest.giver_id) if quest.giver_id in groups["npcs"] else None
            return set(quest.prerequisites) <= completable and (quest.discovered or giver and giver.location_id in accessible)
        if c.kind == "flag":
            return c.target in possible_flags
        if c.kind == "standing":
            return possible_standing.get(c.target, 0) >= c.amount
        if c.kind == "item":
            return c.target in possible_items
        if c.kind == "visited":
            return c.target in accessible
        if c.kind == "kills":
            return c.target in possible_kills
        if c.kind == "level":
            return possible_level >= c.amount
        return c.kind == "turn"

    def enabled_table(t):
        return t.region_id in reachable_regions and (t.location_id is None or t.location_id in accessible) and all(can_condition(c) for c in t.conditions)

    possible_recipes: set[str] = set()
    for _ in range(len(spec.locations) + len(spec.quests) + len(spec.crafting) + len(spec.world_events) + 1):
        for loc in spec.locations:
            if loc.id in accessible:
                possible_items.update(loc.market_items)
        for table in spec.encounters:
            if enabled_table(table):
                possible_kills.update(table.enemy_counts)
                for eid in table.enemy_counts:
                    if eid in groups["enemies"]:
                        possible_items.update(index[eid].loot)
        for recipe in spec.crafting:
            if set(recipe.ingredients) <= possible_items:
                possible_items.update(recipe.outputs)
                possible_recipes.add(recipe.id)
        for q in spec.quests:
            giver = index.get(q.giver_id) if q.giver_id in groups["npcs"] else None
            if not giver or giver.location_id not in accessible or not set(q.prerequisites) <= completable:
                continue
            possible = True
            for o in q.objectives:
                required_locations = []
                if o.kind in ("visit", "pay"):
                    required_locations = [o.target_id]
                elif o.kind in ("talk", "escort") and o.target_id in groups["npcs"]:
                    required_locations = [index[o.target_id].location_id]
                elif o.kind == "kill":
                    possible &= o.target_id in possible_kills
                elif o.kind == "collect":
                    possible &= o.target_id in possible_items
                elif o.kind == "craft":
                    possible &= o.target_id in possible_recipes
                if o.destination_id:
                    required_locations.append(o.destination_id)
                possible &= set(required_locations) <= accessible
            if possible:
                completable.add(q.id)
        actions = [a for q in spec.quests if q.id in completable for a in q.reward_actions]
        actions.extend(a for loc in spec.locations if loc.id in accessible for a in loc.entry_actions)
        for event in spec.world_events:
            if all(can_condition(c) for c in event.conditions):
                actions.extend(event.actions)
        # Reachable one-shot conversations may also open world paths.
        for npc in spec.npcs:
            if npc.location_id in accessible and npc.dialogue_id in groups["dialogues"]:
                actions.extend(a for n in index[npc.dialogue_id].nodes for c in n.choices
                               if all(can_condition(cond) for cond in c.conditions) for a in c.actions)
        possible_standing = {}
        potential_xp = 0
        for a in actions:
            if a.kind == "flag" and a.amount > 0:
                possible_flags.add(a.target)
            elif a.kind == "grant_item":
                possible_items.add(a.target)
            elif a.kind == "standing":
                possible_standing[a.target] = possible_standing.get(a.target, 0) + a.amount
            elif a.kind == "xp":
                potential_xp += a.amount
            elif a.kind == "spawn" and a.target in groups["enemies"]:
                possible_kills.add(a.target); possible_items.update(index[a.target].loot)
        potential_xp += sum(index[eid].xp * count for table in spec.encounters if enabled_table(table)
                            for eid, count in table.enemy_counts.items() if eid in groups["enemies"])
        prog = index.get(p.progression_id) if p.progression_id in groups["progression"] else None
        if prog:
            spent = 0; possible_level = 1
            while possible_level < 100 and spent + possible_level * prog.xp_per_level <= potential_xp:
                spent += possible_level * prog.xp_per_level; possible_level += 1
        for loc in spec.locations:
            if loc.region_id in reachable_regions and all(can_condition(c) for c in loc.locked_by):
                accessible.add(loc.id)
            if loc.region_id in reachable_regions and any(a.kind == "unlock" and a.target == loc.id for a in actions):
                accessible.add(loc.id)
    for loc in spec.locations:
        if loc.id not in accessible:
            fail("inaccessible_area", loc.id, "No validated progression path opens this area")
    for q in spec.quests:
        if q.id not in completable:
            fail("unreachable_quest", q.id, "Giver, prerequisites or objectives cannot be reached")

    # Conservative baseline combat check: a free attack must sustain ordinary play.
    usable = [a for a in spec.abilities if a.id in p.ability_ids and not any(a.cost.values())]
    if not any(e.kind == "damage" for a in usable for e in a.effects):
        fail("zero_damage_loop", "player", "Player needs a free damaging ability")
    for enemy in spec.enemies:
        armor = enemy.stats.get(rules.armor_stat_id, 0)
        can_hurt = False
        for a in usable:
            for e in a.effects:
                if e.kind == "damage":
                    raw = e.amount + a.power_scale * p.stats.get(rules.power_stat_id, 0)
                    resist = enemy.resistances.get(e.damage_type, 0)
                    can_hurt |= max(1, raw - armor) * (100 - resist) // 100 > 0
        if not can_hurt:
            fail("unkillable_enemy", enemy.id, "No sustainable player attack can damage this enemy")
        if enemy.behavior != "passive":
            enemy_free = [index[aid] for aid in enemy.ability_ids if aid in groups["abilities"] and not any(index[aid].cost.values())]
            if not any(e.kind == "damage" for a in enemy_free for e in a.effects):
                fail("zero_damage_loop", enemy.id, "Hostile enemy needs a sustainable damaging ability")
    for entity in spec.entities():
        if spec.metadata.source_chunk_ids and not set(entity.provenance.source_chunk_ids) <= set(spec.metadata.source_chunk_ids):
            fail("invalid_provenance", entity.id, "Provenance cites an unknown source chunk")
        if entity.visual.asset_id:
            ref(entity.visual.asset_id, "assets", entity.id)
        refs(entity.visual.animation_ids, "assets", entity.id)
    for asset in spec.assets:
        if asset.fallback.asset_id:
            fail("invalid_asset", asset.id, "Fallback must be self-contained")
        if asset.path:
            from pathlib import PurePosixPath
            path = PurePosixPath(asset.path)
            if path.is_absolute() or ".." in path.parts or "\\" in asset.path or ":" in asset.path:
                fail("invalid_asset", asset.id, "Asset path must stay inside the package")
            if not asset.sha256:
                fail("invalid_asset", asset.id, "Asset files require a checksum")

    if check_maps and not any(i.code == "invalid_reference" for i in issues):
        try:
            maps = build_maps(spec)
            for region in spec.regions:
                points = maps[region.id].points
                reachable = maps[region.id].reachable()
                for eid, xy in points.items():
                    if tuple(xy) not in reachable:
                        fail("inaccessible_area", eid, "Location is physically disconnected")
            for key, m in maps.items():
                if "boss" in m.points and tuple(m.points["boss"]) not in m.reachable():
                    fail("invalid_spawn", key, "Boss cannot be reached from stairs")
        except ValueError as exc:
            fail("invalid_topology", "maps", str(exc))
    return issues


def require_valid(spec: RealmSpec, *, check_maps: bool = True) -> RealmSpec:
    issues = validate_realm(spec, check_maps=check_maps)
    if any(i.severity == "error" for i in issues):
        raise InvalidRealm(issues)
    return spec


def repair_safe(spec: RealmSpec) -> tuple[RealmSpec, list[str]]:
    """Only noncreative repairs: use valid fallback art if optional art is absent."""
    data = spec.model_dump(mode="json")
    ids = {a.id for a in spec.assets}
    changes: list[str] = []
    for entity in spec.entities():
        if entity.visual.asset_id and entity.visual.asset_id not in ids:
            changes.append(f"{entity.id}: removed missing optional asset {entity.visual.asset_id}")
    def visit(node):
        if isinstance(node, dict):
            if "visual" in node and node["visual"].get("asset_id") not in ids:
                node["visual"]["asset_id"] = None
            for v in node.values():
                visit(v)
        elif isinstance(node, list):
            for v in node:
                visit(v)
    visit(data)
    return RealmSpec.model_validate(data), changes
