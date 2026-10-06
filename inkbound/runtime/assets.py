"""Presentation resources, with safe glyph/synthesized-sound fallbacks."""
from __future__ import annotations

import json

import pygame

from inkbound.realm.package import RealmPackage, safe_file


class Assets:
    def __init__(self, package: RealmPackage):
        self.package = package
        self.definitions = {asset.id: asset for asset in package.spec.assets}
        self.images = {}; self.sounds = {}
        self.font_path = None; self.accent = None
        self.loop_started = False
        if package.root is None: return
        for asset in self.definitions.values():
            if not asset.path: continue
            path = safe_file(package.root, asset.path)
            try:
                if asset.kind in ("sprite", "portrait", "tile", "icon", "background", "animation"):
                    self.images[asset.id] = pygame.image.load(str(path)).convert_alpha()
                elif asset.kind in ("music", "ambient", "combat_sound"):
                    self.sounds[asset.id] = pygame.mixer.Sound(str(path))
                elif asset.kind == "font":
                    pygame.font.Font(str(path), 15); self.font_path = str(path)
                elif asset.kind == "ui_theme":
                    value = json.loads(path.read_text()).get("accent")
                    if isinstance(value, str) and len(value) == 7:
                        self.accent = pygame.Color(value)
            except (pygame.error, OSError, ValueError):
                # Corrupt checksummed media is still permitted to use its glyph fallback.
                continue

    def image_for(self, entity):
        aid = next((x for x in entity.visual.animation_ids if x in self.images), entity.visual.asset_id)
        source = self.images.get(aid)
        if source is None: return None
        asset = self.definitions[aid]
        if asset.kind == "animation" and asset.animation_frames > 1:
            width = source.get_width() // asset.animation_frames
            if width > 0:
                frame = pygame.time.get_ticks() * asset.animation_fps // 1000 % asset.animation_frames
                return source.subsurface((frame * width, 0, width, source.get_height()))
        return source

    def ambience(self, enabled):
        if not enabled:
            for sound in self.sounds.values(): sound.stop()
            self.loop_started = False
        elif not self.loop_started:
            for asset in self.definitions.values():
                if asset.kind in ("ambient", "music") and asset.id in self.sounds:
                    self.sounds[asset.id].play(loops=-1)
            self.loop_started = True

    def combat(self):
        for asset in self.definitions.values():
            if asset.kind == "combat_sound" and asset.id in self.sounds:
                self.sounds[asset.id].play(); return True
        return False
