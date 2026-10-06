import json
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame as pg
import pytest

from inkbound.authoring.assets import ProceduralAssets, build_assets
from inkbound.realm.models import RealmSpec
from inkbound.realm.package import RealmPackage
from inkbound.runtime.engine import Engine
from inkbound.runtime.ui import App, TABS


def test_settings_persist_and_malformed_settings_fall_back(spec, tmp_path):
    app = App(Engine(RealmPackage(spec)), tmp_path / "save.json")
    app.tab = "SETTINGS"
    app.key(pg.K_g); app.key(pg.K_s); app.key(pg.K_PLUS)
    settings = (app.ascii, app.sound, app.tile)
    pg.quit()
    resumed = App(Engine(RealmPackage(spec)), tmp_path / "save.json")
    assert (resumed.ascii, resumed.sound, resumed.tile) == settings
    pg.quit()
    (tmp_path / "settings.json").write_text("[]")
    recovered = App(Engine(RealmPackage(spec)), tmp_path / "save.json")
    assert (recovered.ascii, recovered.sound, recovered.tile) == (False, True, 22)
    pg.quit()


def test_every_tab_overlay_and_resize_renders_without_advancing_simulation(spec, tmp_path):
    e = Engine(RealmPackage(spec)); app = App(e, tmp_path / "save.json", size=(840, 640)); app.sound = False
    initial = e.state.model_dump()
    for tab in TABS:
        app.tab = tab; app.draw()
        assert app.screen.get_size() == (840, 640)
    app.tab = "MAP"
    for overlay in ("journal", "abilities", "craft", "oath", "shop", "caravan"):
        app.open_overlay(overlay); app.draw(); app.key(pg.K_ESCAPE)
    assert e.state == type(e.state).model_validate(initial)
    app.key(pg.K_F5)
    assert (tmp_path / "save.json").exists()
    app.ascii = True; app.draw()
    pg.quit()


def test_optional_asset_generation_and_missing_provider_fallback(spec, tmp_path):
    data = spec.model_dump(mode="json")
    data["assets"][0].update(kind="sprite", provider="procedural")
    data["player"]["visual"]["asset_id"] = data["assets"][0]["id"]
    generated, report = build_assets(RealmSpec.model_validate(data), tmp_path / "media", {"procedural": ProceduralAssets()})
    assert report and generated.assets[0].path and generated.assets[0].sha256
    path = RealmPackage(generated).write(tmp_path / "package", tmp_path / "media")
    app = App(Engine(RealmPackage.load(path)), tmp_path / "state.json")
    assert app.assets.image_for(app.engine.spec.player) is not None
    app.draw(); pg.quit()
    fallback, report = build_assets(RealmSpec.model_validate(data), tmp_path / "absent", {})
    assert fallback.assets[0].provider == "fallback" and not fallback.assets[0].path
    RealmPackage(fallback).write(tmp_path / "fallback")


def test_frontier_shifts_live_content_and_save_resume(spec, tmp_path):
    e = Engine(RealmPackage(spec))
    old = list(e.current_map.points["location.home"])
    original_ids = {entity.id for entity in spec.entities()}
    assert e.expand("left")
    assert e.current_map.points["location.home"] == [old[0] + 16, old[1]]
    assert e.current_map.walkable(e.player.x, e.player.y)
    assert e.expand("top")
    assert e.current_map.points["location.home"] == [old[0] + 16, old[1] + 16]
    assert original_ids == {entity.id for entity in e.spec.entities()}
    e.save(tmp_path / "expanded.json")
    resumed = Engine.load(e.package, tmp_path / "expanded.json")
    assert resumed.state == e.state
    resumed.expand("right"); e.expand("right")
    assert resumed.state == e.state


def test_malformed_saved_map_rejected_without_index_error(spec, tmp_path):
    e = Engine(RealmPackage(spec)); p = tmp_path / "bad.json"; e.save(p)
    data = json.loads(p.read_text()); data["maps"][e.player.map_id]["grid"][e.player.y] = ""
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="map"):
        Engine.load(e.package, p)


def test_wrong_kind_references_report_validation_error(fantasy_data):
    from inkbound.realm.validation import validate_realm
    fantasy_data["player"]["progression_id"] = "enemy.guard"
    fantasy_data["player"]["starting_items"] = {"npc.guide": 1}
    fantasy_data["world_rules"]["health_resource_id"] = "item.weapon"
    issues = validate_realm(RealmSpec.model_validate(fantasy_data))
    assert "invalid_reference" in {i.code for i in issues}
