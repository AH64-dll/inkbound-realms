"""Pygame presentation for packages, retaining Inkbound's tiles/tabs/compass."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pygame as pg

from inkbound.runtime.engine import Engine
from inkbound.runtime.assets import Assets
from legacy.ascii_rpg.src.sfx import play, set_enabled
from legacy.ascii_rpg.src.ui import THEME, _tile_icon, fit


TABS = ["MAP", "CHARACTERS", "BOOKS", "SAVES", "SETTINGS", "INVENTORY", "DATA"]


class App:
    def __init__(self, engine: Engine, save_path: str | Path = "saves/realm.json", *, size=(1180, 800)):
        self.engine = engine
        self.save_path = Path(save_path)
        self.settings_path = self.save_path.parent / "settings.json"
        self.tab = "MAP"
        self.overlay: str | None = None
        self.selection = 0
        self.panel_scroll = 0
        self.dialogue_scroll = 0
        self._minimap_cache = None
        self.shop_mode = "buy"
        self.ascii = False
        self.sound = True
        self.fullscreen = False
        self.tile = 22
        try:
            settings = json.loads(self.settings_path.read_text())
            if type(settings.get("ascii")) is bool: self.ascii = settings["ascii"]
            if type(settings.get("sound")) is bool: self.sound = settings["sound"]
            if type(settings.get("tile")) is int and 16 <= settings["tile"] <= 32: self.tile = settings["tile"]
        except (OSError, ValueError, AttributeError):
            pass
        set_enabled(self.sound)
        self.running = True
        self.tracked = None
        pg.init()
        self.screen = pg.display.set_mode(size, pg.RESIZABLE)
        pg.display.set_caption(f"Inkbound Realms — {engine.spec.metadata.title}")
        self.assets = Assets(engine.package)
        self.font = pg.font.Font(self.assets.font_path, 15) if self.assets.font_path else pg.font.SysFont("DejaVu Sans Mono,monospace", 15)
        self.tiny = pg.font.SysFont("DejaVu Sans Mono,monospace", 12)
        self.big = pg.font.SysFont("DejaVu Sans Mono,monospace", 24, bold=True)
        self.glyph_font = pg.font.SysFont("DejaVu Sans Mono,monospace", 19)
        self.tab_rects: list[tuple[pg.Rect, str]] = []
        self.acc = self.assets.accent or pg.Color(engine.spec.player.visual.color)

    def text(self, text, x, y, width, color=None, font=None):
        font = font or self.font
        self.screen.blit(font.render(fit(font, str(text), max(0, width)), True, color or THEME["text"]), (x, y))

    def wrap(self, text, width, font=None):
        font = font or self.font
        lines = []
        for paragraph in str(text).splitlines() or [""]:
            current = ""
            for word in paragraph.split():
                if font.size(current + " " + word)[0] > width and current:
                    lines.append(current); current = ""
                if font.size(word)[0] > width:
                    if current: lines.append(current); current = ""
                    part = ""
                    for char in word:
                        if font.size(part + char)[0] > width and part:
                            lines.append(part); part = ""
                        part += char
                    current = part
                else:
                    current = (current + " " + word).strip()
            lines.append(current)
        return lines

    def card(self, rect, color=None):
        pg.draw.rect(self.screen, THEME["panel"], rect, border_radius=7)
        pg.draw.rect(self.screen, color or THEME["line"], rect, 1, border_radius=7)

    def bar(self, label, value, cap, x, y, width, color):
        pg.draw.rect(self.screen, THEME["panel2"], (x, y, width, 18), border_radius=7)
        pg.draw.rect(self.screen, color, (x, y, max(0, int(width * min(1, value / max(1, cap)))), 18), border_radius=7)
        self.text(f"{label} {value}/{cap}", x + 6, y, width - 12, THEME["text"], self.tiny)

    def draw(self):
        w, h = self.screen.get_size()
        self.screen.fill(THEME["bg"])
        self.tab_rects = []
        x = 6
        for i, tab in enumerate(TABS):
            label = f"{i + 1}:{tab}"
            tw = self.tiny.size(label)[0] + 18
            rect = pg.Rect(x, 6, tw, 26)
            pg.draw.rect(self.screen, THEME["panel2"] if tab == self.tab else THEME["panel"], rect, border_radius=4)
            self.text(label, x + 8, 12, tw - 12, self.acc if tab == self.tab else THEME["mid"], self.tiny)
            self.tab_rects.append((rect, tab)); x += tw + 5
        self.text(self.engine.spec.metadata.title, x + 8, 12, w - x - 18, self.acc, self.tiny)
        if self.tab == "MAP":
            self.draw_map(w, h)
        else:
            self.draw_panel(w, h)
        if self.engine.state.active_dialogue_id:
            self.draw_dialogue(w, h)
        elif self.overlay:
            self.draw_overlay(w, h)
        if not self.engine.alive(self.engine.player):
            rect = pg.Rect(w // 2 - 230, h // 2 - 55, 460, 110)
            self.card(rect, THEME["red"])
            self.text("FALLEN", rect.x + 20, rect.y + 15, 420, THEME["red"], self.big)
            self.text("R returns to the hearth. Your deeds remain.", rect.x + 20, rect.y + 62, 420)

    def draw_map(self, w, h):
        e = self.engine; p = e.player; m = e.current_map
        side = min(350, max(290, w // 3))
        map_w, map_h = w - side - 18, h - 210
        cols, rows = max(8, map_w // self.tile), max(8, map_h // self.tile)
        map_w, map_h = cols * self.tile, rows * self.tile
        x0 = max(0, min(max(0, len(m.grid[0]) - cols), p.x - cols // 2))
        y0 = max(0, min(max(0, len(m.grid) - rows), p.y - rows // 2))
        map_rect = pg.Rect(6, 40, map_w, map_h)
        self.card(map_rect)
        self.screen.set_clip(map_rect)
        for sy in range(rows):
            for sx in range(cols):
                x, y = x0 + sx, y0 + sy
                if y >= len(m.grid) or x >= len(m.grid[0]): continue
                glyph = m.grid[y][x]; X, Y = 6 + sx * self.tile, 40 + sy * self.tile
                if self.ascii:
                    color = {"O": THEME["gold"], "D": self.acc, "*": THEME["cyan"], "=": (155, 128, 75), "T": (65, 145, 77), "~": (60, 110, 180), "#": (145, 140, 120)}.get(glyph, THEME["faint"])
                    self.text(glyph, X + 2, Y, self.tile, color, self.glyph_font)
                else:
                    _tile_icon(pg, self.screen, {"R": "#", "C": "C"}.get(glyph, glyph), X, Y, self.tile, x, y)
        for npc in e.spec.npcs:
            xy = e.state.npc_positions.get(npc.id)
            if xy and e.npc_map_id(npc) == p.map_id and e.npc_available(npc):
                self.draw_actor(npc, *xy, x0, y0, npc.visual.color)
        for actor in e.state.actors.values():
            if actor.map_id != p.map_id or not e.alive(actor): continue
            definition = e.index[actor.definition_id]
            self.draw_actor(definition, actor.x, actor.y, x0, y0, THEME["green"] if actor.friendly else THEME["red"])
            if actor.telegraph:
                self.text("!", 6 + (actor.x - x0) * self.tile, 34 + (actor.y - y0) * self.tile, self.tile, THEME["gold"], self.tiny)
            if actor.id == e.state.target_id:
                pg.draw.rect(self.screen, THEME["gold"], (6 + (actor.x - x0) * self.tile, 40 + (actor.y - y0) * self.tile, self.tile, self.tile), 1)
        for drop in e.state.pending_loot.values():
            if drop.map_id == p.map_id:
                self.text("$", 6 + (drop.x - x0) * self.tile, 40 + (drop.y - y0) * self.tile, self.tile, THEME["gold"], self.glyph_font)
        self.draw_actor(e.spec.player, p.x, p.y, x0, y0, e.spec.player.visual.color)
        target = self.quest_target()
        if target and target[0] == p.map_id:
            dx, dy = target[1] - p.x, target[2] - p.y
            compass = ">" if abs(dx) > abs(dy) and dx > 0 else "<" if abs(dx) > abs(dy) else "v" if dy > 0 else "^"
            self.text(f"{compass} {target[3]} — {abs(dx) + abs(dy)} steps", 16, map_rect.bottom - 25, map_w - 20, THEME["gold"], self.tiny)
        self.screen.set_clip(None)
        sx = map_rect.right + 8; sw = w - sx - 6
        self.card(pg.Rect(sx, 40, sw, h - 48))
        y = 50
        self.text(e.player_name, sx + 12, y, sw - 24, self.acc); y += 22
        self.text(e.spec.player.archetype, sx + 12, y, sw - 24, THEME["mid"], self.tiny); y += 22
        self.text(f"Level {e.state.level}  {e.state.gold} {e.spec.economy.currency_name}", sx + 12, y, sw - 24, THEME["gold"], self.tiny); y += 21
        self.text(f"Day {e.day}  ({p.x},{p.y})", sx + 12, y, sw - 24, THEME["dim"], self.tiny); y += 26
        for rid, cap in p.caps.items():
            self.bar(e.index[rid].name, p.resources[rid], cap, sx + 10, y, sw - 20, THEME["hp"] if rid == e.health_id else THEME["mana"]); y += 24
        prog = e.index[e.spec.player.progression_id]
        self.bar("Experience", e.state.xp, e.state.level * prog.xp_per_level, sx + 10, y, sw - 20, THEME["xp"]); y += 30
        if p.shield:
            self.text(f"Protection buffer: {p.shield}", sx + 12, y, sw - 24, self.acc, self.tiny); y += 20
        for qid in e.active_quests()[:4]:
            q = e.index[qid]
            self.text(("MAIN " if q.main else "TALE ") + q.name, sx + 12, y, sw - 24, THEME["gold"], self.tiny); y += 19
            for n, obj in zip(e.quest_progress(qid), q.objectives):
                self.text(f"{obj.kind}: {e.index[obj.target_id].name} {n}/{obj.count}", sx + 18, y, sw - 30, THEME["mid"], self.tiny); y += 18
            y += 7
        foes = e.threats()
        nearby = [a for a in foes if e.distance(p, a) <= 7]
        if nearby:
            self.text("NEARBY THREATS [I marks]", sx + 12, y, sw - 24, THEME["red"], self.tiny); y += 20
            for a in nearby[:3]:
                self.text(f"{e.index[a.definition_id].name} {a.resources[e.health_id]} HP", sx + 12, y, sw - 24, THEME["mid"], self.tiny); y += 18
        # Same live minimap/viewport/player relationship as the original game.
        mm_h = min(140, max(60, h - y - 70)); mm_y = max(y + 15, h - mm_h - 45)
        self.minimap(sx + 12, mm_y, sw - 24, mm_h, x0, y0, cols, rows)
        log_y = map_rect.bottom + 9
        self.card(pg.Rect(6, log_y, map_w, h - log_y - 8))
        for i, line in enumerate(["Arrows/WASD move · E interact · J tales · C abilities · K craft", "A attack · H heavy/heal · Q quick · D guard · F flee · I mark", "B market · Z rest · T track · F5 save · F11 fullscreen · Esc close"]):
            self.text(line, 14, log_y + 8 + i * 17, map_w - 16, THEME["dim"], self.tiny)
        visible = max(1, (h - log_y - 67) // 18)
        for i, line in enumerate(e.state.messages[-visible:]):
            self.text(line, 14, log_y + 66 + i * 18, map_w - 16, THEME["text"], self.tiny)

    def draw_actor(self, definition, x, y, x0, y0, color):
        X, Y = 6 + (x - x0) * self.tile, 40 + (y - y0) * self.tile
        asset = self.assets.image_for(definition)
        if asset is not None and not self.ascii:
            self.screen.blit(pg.transform.smoothscale(asset, (self.tile, self.tile)), (X, Y))
        elif self.ascii:
            self.text(definition.visual.glyph, X + 2, Y, self.tile, color, self.glyph_font)
        else:
            if definition.id == self.engine.spec.player.id:
                _tile_icon(pg, self.screen, "@", X, Y, self.tile, x, y)
            else:
                pg.draw.circle(self.screen, pg.Color(color), (X + self.tile // 2, Y + self.tile // 2), self.tile // 3)
                self.text(definition.visual.glyph, X + 4, Y + 1, self.tile, THEME["bg"], self.tiny)

    def minimap(self, x, y, width, height, x0, y0, cols, rows):
        e = self.engine; m = e.current_map; mw, mh = len(m.grid[0]), len(m.grid)
        cache_key = (m.id, id(m.grid), mw, mh)
        if self._minimap_cache and self._minimap_cache[0] == cache_key:
            surface = self._minimap_cache[1]
        else:
            surface = pg.Surface((mw, mh))
            for yy, row in enumerate(m.grid):
                for xx, c in enumerate(row):
                    surface.set_at((xx, yy), {"~": (30, 75, 160), "T": (35, 95, 45), "^": (115, 115, 125), "#": (95, 90, 80), "=": (165, 145, 80), "O": (255, 215, 0), "D": (150, 95, 200)}.get(c, (33, 45, 40)))
            self._minimap_cache = (cache_key, surface)
        self.screen.blit(pg.transform.scale(surface, (width, height)), (x, y))
        px = x + e.player.x * width / mw; py = y + e.player.y * height / mh
        pg.draw.rect(self.screen, THEME["dim"], (x + x0 * width / mw, y + y0 * height / mh, min(cols, mw) * width / mw, min(rows, mh) * height / mh), 1)
        pg.draw.circle(self.screen, THEME["text"], (int(px), int(py)), 3)

    def quest_target(self):
        e = self.engine
        candidates = e.active_quests()
        if not candidates: return None
        qid = self.tracked if self.tracked in candidates else candidates[0]
        q = e.index[qid]
        target = e.index[q.giver_id].location_id
        for n, obj in zip(e.quest_progress(qid), q.objectives):
            if n < obj.count:
                if obj.kind in ("visit", "pay"): target = obj.target_id
                elif obj.kind in ("talk", "escort"): target = obj.destination_id or e.index[obj.target_id].location_id
                elif obj.kind in ("kill", "collect"):
                    enemy_ids = [obj.target_id] if obj.kind == "kill" else [a.id for a in e.spec.enemies if obj.target_id in a.loot]
                    table = next((t for t in e.spec.encounters if set(t.enemy_counts) & set(enemy_ids)), None)
                    if table: target = table.location_id or table.region_id
                break
        if target in e.current_map.points:
            return (e.player.map_id, *e.current_map.points[target], q.name)
        if e.player.map_id == target:
            live = e.threats()
            if live: return (target, live[0].x, live[0].y, q.name)
        if e.state.return_stack:
            return (e.player.map_id, *e.current_map.entrance, q.name)
        return None

    def panel_lines(self):
        e = self.engine
        if self.tab == "CHARACTERS":
            p = e.spec.player
            lines = [p.name + " — " + p.archetype, "", p.background, p.appearance, "", "Motivations: " + "; ".join(p.motivations), "Traits: " + "; ".join(p.personality), ""]
            lines += [f"{e.index[k].name}: {e.stat(e.player, k)}" for k in e.player.stats]
            lines += ["", "ABILITIES"] + [e.index[aid].name + ": " + e.index[aid].description for aid in e.known_abilities()]
            lines += ["", "PASSIVES"] + [p.name + ": " + p.description for p in e.spec.player.passives]
            lines += ["", "PRACTICE"] + [f"{s.name}: {e.state.skills.get(s.id, 0)}/{s.threshold}" + (" — mastered" if s.id in e.state.mastered_skills else "") for s in e.spec.skills]
            return lines
        if self.tab == "BOOKS":
            direction = e.spec.creative_direction
            return [e.spec.metadata.source_title, "", direction.interpretation.genre, "Tone: " + ", ".join(direction.interpretation.tone), "", "Themes: " + "; ".join(direction.interpretation.themes), "", direction.gameplay_identity, "", direction.world_bible]
        if self.tab == "SAVES":
            return ["F5 saves this world. F9 resumes the saved world.", "", "Your character, choices, inventory and discovered places travel together.", "", f"Current adventure: {e.spec.metadata.title}", f"Day {e.day}, level {e.state.level}", "", "A different realm has its own save."]
        if self.tab == "SETTINGS":
            return ["G switches icons / ASCII: " + ("ASCII" if self.ascii else "icons"), "S toggles retro sound: " + ("on" if self.sound else "off"), "F11 toggles fullscreen", "+ / - changes tile size", "", "MAP: arrows/WASD move, E interact, J tales, T track", "FIGHT: A attack, H heavy, Q quick, D guard, F flee, I mark", "C opens abilities; R uses a ranged action or revives if fallen", "Z rests, B market, K crafting, O faction oath", "INVENTORY: Up/Down, Enter equips/uses, U removes worn gear", "MARKET: Left/Right buy/sell, Up/Down, Enter trades", "Esc closes the current conversation or panel"]
        if self.tab == "INVENTORY":
            worn = [f"{e.index[slot].name}: {e.index[eid].name}" for slot, eid in e.state.equipment.items()]
            pack = [f"{'>' if i == self.selection else ' '} {n} × {e.index[eid].name} — {e.index[eid].description}" for i, (eid, n) in enumerate(e.state.inventory.items())]
            return ["WORN GEAR [U removes selected worn slot]", *worn, "", "PACK [Enter equips or uses]", *pack]
        if self.tab == "DATA":
            lines = ["ANNALS", *e.state.annals, "", "POWERS"]
            lines += [f"{f.name}: standing {e.state.standing.get(f.id, 0)} — {f.ideology}" for f in e.spec.factions]
            lines += ["", "WHY THIS REALM EXISTS"]
            for entity in e.spec.entities():
                lines.extend([entity.name + ": " + ", ".join(entity.provenance.concepts), entity.provenance.rationale, ""])
            return lines
        return []

    def draw_panel(self, w, h):
        self.card(pg.Rect(8, 42, w - 16, h - 51))
        lines = [line for item in self.panel_lines() for line in self.wrap(item, w - 52)]
        self.panel_scroll = min(self.panel_scroll, max(0, len(lines) - (h - 90) // 22))
        for i, line in enumerate(lines[self.panel_scroll:self.panel_scroll + (h - 90) // 22]):
            self.text(line, 24, 57 + i * 22, w - 48, THEME["gold"] if line.isupper() else None)
        self.text("Up/Down scroll · 1–7 tabs · F5 save · F9 load", 24, h - 28, w - 48, THEME["dim"], self.tiny)

    def overlay_rows(self):
        e = self.engine
        if self.overlay == "abilities":
            return [(aid, f"{i + 1}. {e.index[aid].name} — " + ", ".join(f"{n} {e.index[r].name}" for r, n in e.index[aid].cost.items()) + f" (reach {e.index[aid].range})") for i, aid in enumerate(e.known_abilities())]
        if self.overlay == "craft":
            return [(r.id, r.name + " — " + ", ".join(f"{n} {e.index[eid].name}" for eid, n in r.ingredients.items())) for r in e.spec.crafting]
        if self.overlay == "shop":
            loc = e.location_here()
            if not loc or loc.kind != "settlement": return []
            items = loc.market_items if self.shop_mode == "buy" else e.state.inventory
            return [(eid, f"{e.index[eid].name} — {e.price(eid, self.shop_mode == 'buy')} {e.spec.economy.currency_name}") for eid in items]
        if self.overlay == "journal":
            rows = []
            for q in e.spec.quests:
                if q.id not in e.state.quests_known: continue
                status = "COMPLETE" if q.id in e.state.quests_done else "FAILED" if q.id in e.state.quests_failed else "ACTIVE" if q.id in e.active_quests() else "WAITING"
                rows.append((q.id, f"[{status}] {q.name} — {q.description}"))
            return rows
        if self.overlay == "oath":
            return [(f.id, f.name + " — " + f.ideology) for f in e.spec.factions]
        if self.overlay == "caravan":
            rows = [(loc.id, f"{loc.name} — {e.spec.economy.caravan_price} {e.spec.economy.currency_name}") for loc in e.spec.locations if loc.kind == "settlement" and loc.id in e.state.visited]
            if e.player.map_id in {region.id for region in e.spec.regions}:
                rows.extend((rid, "Route to " + e.index[rid].name) for rid in e.index[e.player.map_id].neighbor_ids)
            return rows
        return []

    def draw_overlay(self, w, h):
        rect = pg.Rect(max(20, w // 8), max(65, h // 7), w - max(40, w // 4), h - max(130, h // 3))
        self.card(rect, self.acc)
        title = self.overlay.upper() + (" — " + self.shop_mode.upper() if self.overlay == "shop" else "")
        self.text(title, rect.x + 18, rect.y + 15, rect.width - 36, self.acc, self.big)
        rows = self.overlay_rows(); self.selection = min(self.selection, max(0, len(rows) - 1))
        y = rect.y + 56
        first = max(0, self.selection - 5)
        for i, (_, text) in enumerate(rows[first:], first):
            wrapped = self.wrap(text, rect.width - 52)
            if y + len(wrapped) * 21 >= rect.bottom - 42: break
            for j, line in enumerate(wrapped):
                self.text(("> " if i == self.selection and j == 0 else "  ") + line, rect.x + 18, y, rect.width - 36, THEME["gold"] if i == self.selection else None)
                y += 21
            y += 6
        self.text("Up/Down selects · Enter acts · Esc closes" + (" · Left/Right buy/sell" if self.overlay == "shop" else ""), rect.x + 18, rect.bottom - 27, rect.width - 36, THEME["dim"], self.tiny)

    def draw_dialogue(self, w, h):
        node = self.engine.dialogue_node()
        rect = pg.Rect(w // 8, h // 6, w * 3 // 4, h * 2 // 3)
        self.card(rect, self.acc)
        npc = self.engine.index[self.engine.state.active_npc_id]
        self.text(npc.name, rect.x + 20, rect.y + 15, rect.width - 40, self.acc, self.big)
        lines = [(line, THEME["text"]) for line in self.wrap(node.text, rect.width - 40)]
        lines.append(("", THEME["text"]))
        choices = [c for c in node.choices if self.engine.conditions(c.conditions)]
        for i, choice in enumerate(choices):
            for j, line in enumerate(self.wrap(choice.text, rect.width - 65)):
                lines.append(((f"{i + 1}. " if j == 0 else "   ") + line, THEME["gold"]))
        count = max(1, (rect.height - 105) // 23)
        self.dialogue_scroll = min(self.dialogue_scroll, max(0, len(lines) - count))
        for i, (line, color) in enumerate(lines[self.dialogue_scroll:self.dialogue_scroll + count]):
            self.text(line, rect.x + 20, rect.y + 58 + i * 23, rect.width - 40, color)
        self.text("Choose a number · Up/Down scroll · Esc returns", rect.x + 20, rect.bottom - 30, rect.width - 40, THEME["dim"], self.tiny)

    def key(self, key):
        before = self.engine.state.turn
        hp = self.engine.player.resources[self.engine.health_id]
        level = self.engine.state.level
        completed = len(self.engine.state.quests_done)
        self._key(key)
        if self.sound:
            if self.engine.state.level > level: play("level")
            elif len(self.engine.state.quests_done) > completed: play("quest")
            elif self.engine.player.resources[self.engine.health_id] < hp: play("hurt")
            elif self.engine.state.turn > before and key in (pg.K_a, pg.K_h, pg.K_q, pg.K_r):
                if not self.assets.combat(): play("hit")

    def _key(self, key):
        e = self.engine
        if key == pg.K_F5:
            e.save(self.save_path); e.log("Adventure saved."); return
        if key == pg.K_F9:
            try: self.engine = Engine.load(e.package, self.save_path)
            except (ValueError, OSError) as exc: e.log(f"Cannot resume: {exc}")
            return
        if key == pg.K_F11:
            self.fullscreen = not self.fullscreen
            self.screen = pg.display.set_mode((0, 0), pg.FULLSCREEN) if self.fullscreen else pg.display.set_mode((1180, 800), pg.RESIZABLE)
            return
        if key == pg.K_ESCAPE:
            e.close_dialogue(); self.overlay = None; return
        if not e.alive(e.player):
            if key == pg.K_r: e.respawn()
            return
        if e.state.active_dialogue_id:
            choices = [c for c in e.dialogue_node().choices if e.conditions(c.conditions)]
            if key == pg.K_DOWN: self.dialogue_scroll += 1
            elif key == pg.K_UP: self.dialogue_scroll = max(0, self.dialogue_scroll - 1)
            elif pg.K_1 <= key <= pg.K_9 and key - pg.K_1 < len(choices):
                e.choose(choices[key - pg.K_1].id); self.dialogue_scroll = 0
            return
        if self.overlay:
            rows = self.overlay_rows()
            if key == pg.K_UP: self.selection = max(0, self.selection - 1)
            elif key == pg.K_DOWN: self.selection = min(max(0, len(rows) - 1), self.selection + 1)
            elif key in (pg.K_LEFT, pg.K_RIGHT) and self.overlay == "shop":
                self.shop_mode = "sell" if self.shop_mode == "buy" else "buy"; self.selection = 0
            elif key == pg.K_RETURN or self.overlay == "abilities" and pg.K_1 <= key <= pg.K_9:
                if self.overlay == "abilities" and pg.K_1 <= key <= pg.K_9: self.selection = key - pg.K_1
                if self.selection < len(rows):
                    eid = rows[self.selection][0]
                    action = {"abilities": e.use_ability, "craft": e.craft, "shop": e.buy if self.shop_mode == "buy" else e.sell,
                              "oath": e.swear, "caravan": lambda eid: e.travel_region(eid) if eid in {r.id for r in e.spec.regions} else e.caravan(eid), "journal": lambda qid: setattr(self, "tracked", qid)}[self.overlay]
                    action(eid); play("ui")
                    if self.overlay in ("abilities", "caravan"): self.overlay = None
            return
        if pg.K_1 <= key <= pg.K_7:
            self.tab = TABS[key - pg.K_1]; self.selection = self.panel_scroll = 0; return
        if self.tab == "SETTINGS":
            if key == pg.K_g: self.ascii = not self.ascii
            elif key == pg.K_s: self.sound = not self.sound; set_enabled(self.sound)
            elif key in (pg.K_PLUS, pg.K_EQUALS): self.tile = min(32, self.tile + 2)
            elif key == pg.K_MINUS: self.tile = max(16, self.tile - 2)
            self.save_settings()
        elif self.tab == "INVENTORY":
            items = list(e.state.inventory)
            if key == pg.K_UP: self.selection = max(0, self.selection - 1)
            elif key == pg.K_DOWN: self.selection = min(max(0, len(items) - 1), self.selection + 1)
            elif key == pg.K_RETURN and items: e.use_item(items[min(self.selection, len(items) - 1)])
            elif key == pg.K_u and e.state.equipment: e.unequip(list(e.state.equipment)[min(self.selection, len(e.state.equipment) - 1)])
        elif self.tab != "MAP":
            if key == pg.K_DOWN: self.panel_scroll += 1
            elif key == pg.K_UP: self.panel_scroll = max(0, self.panel_scroll - 1)
        else:
            threats = [a for a in e.threats() if e.distance(e.player, a) <= 4 and e.line_clear(e.player, a)]
            if key in (pg.K_UP, pg.K_w): e.move(0, -1)
            elif key in (pg.K_DOWN, pg.K_s): e.move(0, 1)
            elif key == pg.K_LEFT or key == pg.K_a and not threats: e.move(-1, 0)
            elif key == pg.K_RIGHT or key == pg.K_d and not threats: e.move(1, 0)
            elif key == pg.K_a: e.use_ability(e.rules.default_ability_id)
            elif key == pg.K_h:
                if threats: e.use_ability(e.rules.default_ability_id, style="heavy")
                else: e.heal()
            elif key == pg.K_q: e.use_ability(e.rules.default_ability_id, style="quick")
            elif key == pg.K_d: e.defend()
            elif key == pg.K_e: e.interact()
            elif key == pg.K_z: e.rest()
            elif key == pg.K_f: e.flee() if threats else self.open_overlay("caravan")
            elif key == pg.K_i:
                candidates = e.threats(); ids = [a.id for a in candidates]
                if ids: e.state.target_id = ids[(ids.index(e.state.target_id) + 1) % len(ids)] if e.state.target_id in ids else ids[0]
            elif key == pg.K_r:
                aid = next((a for a in e.known_abilities() if e.index[a].target == "enemy" and e.index[a].range > 1), None)
                if aid: e.use_ability(aid)
            elif key == pg.K_SPACE: e.tick()
            elif key in (pg.K_c, pg.K_k, pg.K_b, pg.K_j, pg.K_o):
                self.open_overlay({pg.K_c: "abilities", pg.K_k: "craft", pg.K_b: "shop", pg.K_j: "journal", pg.K_o: "oath"}[key])
            elif key == pg.K_t:
                ids = e.active_quests()
                if ids: self.tracked = ids[(ids.index(self.tracked) + 1) % len(ids)] if self.tracked in ids else ids[0]

    def open_overlay(self, name):
        self.overlay = name; self.selection = 0; play("ui")

    def save_settings(self):
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.settings_path.with_suffix(".tmp")
            temporary.write_text(json.dumps({"ascii": self.ascii, "sound": self.sound, "tile": self.tile}))
            os.replace(temporary, self.settings_path)
        except OSError as exc:
            self.engine.log(f"Cannot save settings: {exc}")

    def run(self, *, max_frames: int | None = None, capture: str | Path | None = None):
        clock = pg.time.Clock(); frames = 0; last_save = time.monotonic()
        while self.running:
            for event in pg.event.get():
                if event.type == pg.QUIT: self.running = False
                elif event.type == pg.KEYDOWN: self.key(event.key)
                elif event.type == pg.VIDEORESIZE and not self.fullscreen:
                    self.screen = pg.display.set_mode((max(840, event.w), max(640, event.h)), pg.RESIZABLE)
                elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                    for rect, tab in self.tab_rects:
                        if rect.collidepoint(event.pos): self.tab = tab; self.panel_scroll = 0
                elif event.type == pg.MOUSEWHEEL:
                    self.panel_scroll = max(0, self.panel_scroll - event.y * 3)
            self.assets.ambience(self.sound)
            self.draw(); pg.display.flip(); frames += 1
            if time.monotonic() - last_save >= 60:
                self.engine.save(self.save_path); last_save = time.monotonic()
            if max_frames and frames >= max_frames: self.running = False
            clock.tick(30)
        if capture:
            destination = Path(capture); destination.parent.mkdir(parents=True, exist_ok=True)
            pg.image.save(self.screen, str(destination))
        self.engine.save(self.save_path); self.save_settings(); pg.quit()
