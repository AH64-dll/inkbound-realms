import copy
import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from inkbound.realm.models import AdaptationPolicy, RealmSpec
from inkbound.realm.package import RealmPackage, fingerprint
from inkbound.realm.validation import InvalidRealm, repair_safe, require_valid, validate_realm
from inkbound.runtime.maps import build_maps


def test_all_genres_validate_and_roundtrip(spec):
    require_valid(spec)
    encoded = spec.model_dump_json()
    assert RealmSpec.model_validate_json(encoded) == spec
    schema = RealmSpec.model_json_schema()
    jsonschema.validate(json.loads(encoded), schema)


def test_model_dictionary_mutation_cannot_bypass_package_schema(spec):
    data = spec.model_copy(deep=True)
    data.player.stats[data.world_rules.power_stat_id] = True
    with pytest.raises(ValidationError):
        RealmPackage(data)


def test_boss_phase_ability_requires_resources_the_boss_can_supply(spec):
    data = spec.model_copy(deep=True)
    boss = next(enemy for enemy in data.enemies if enemy.role == "boss")
    phase = data.abilities[0].model_copy(deep=True)
    phase.id = "ability.phase-only"
    phase.cost = {"resource.energy": 1000}
    data.abilities.append(phase)
    boss.phase_ability_ids = [phase.id]
    assert any(issue.code == "unsupported_ability" and issue.path == boss.id for issue in validate_realm(data))


def test_provenance_must_reference_an_ingested_chunk(spec):
    data = spec.model_copy(deep=True)
    data.player.provenance.source_chunk_ids = ["chunk.missing"]
    assert any(issue.code == "invalid_provenance" for issue in validate_realm(data))


@pytest.mark.parametrize("field,value", [("name", "   "), ("description", "A broken\u0000label")])
def test_malformed_ui_text_is_rejected_before_play(spec, field, value):
    data = spec.model_copy(deep=True)
    setattr(data.player, field, value)
    with pytest.raises(InvalidRealm, match="malformed_text"):
        RealmPackage(data)


def test_health_regeneration_cannot_make_baseline_combat_endless(spec):
    data = spec.model_copy(deep=True)
    next(r for r in data.resources if r.id == data.world_rules.health_resource_id).regen = 1000000
    assert any(issue.code == "unkillable_enemy" for issue in validate_realm(data))


@pytest.mark.parametrize("mutation", ["cost", "ally_target"])
def test_default_attack_must_work_on_hostile_targets_without_resource_cost(spec, mutation):
    data = spec.model_copy(deep=True)
    attack = data.index()[data.world_rules.default_ability_id]
    if mutation == "cost": attack.cost = {"resource.energy": 1}
    else: attack.target = "ally"
    assert any(issue.code == "invalid_default_attack" for issue in validate_realm(data))


def test_heavy_default_action_can_overcome_small_health_regeneration(spec):
    data = spec.model_copy(deep=True)
    attack = data.index()[data.world_rules.default_ability_id]
    attack.effects[0].amount = 20
    attack.power_scale = 0
    next(r for r in data.resources if r.id == data.world_rules.health_resource_id).regen = 20
    assert not any(issue.code == "unkillable_enemy" for issue in validate_realm(data))


@pytest.mark.parametrize("mutation", ["overflow", "missing_interior"])
def test_encounter_sources_must_actually_place_the_declared_actors(spec, mutation):
    data = spec.model_copy(deep=True)
    table = data.encounters[0]
    if mutation == "overflow": table.enemy_counts = {data.enemies[0].id: 1000000}
    else: table.location_id = "location.refuge"
    assert any(issue.code == "invalid_spawn" and issue.path == table.id for issue in validate_realm(data))


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(realm_spec_version=2),
    lambda d: d.update(engine_script="print('book code')"),
    lambda d: d["player"].update(stats={"stat.power": True}),
    lambda d: d["abilities"][0]["effects"][0].update(kind="execute_code"),
    lambda d: d["metadata"].update(seed=-1),
])
def test_schema_rejects_untrusted_payloads(fantasy_data, mutation):
    mutation(fantasy_data)
    with pytest.raises(ValidationError):
        RealmSpec.model_validate(fantasy_data)


@pytest.mark.parametrize(("mutation", "code"), [
    (lambda d: d["items"][0].update(id=d["player"]["id"]), "duplicate_id"),
    (lambda d: d["player"].update(progression_id="missing.progression"), "invalid_reference"),
    (lambda d: d["quests"][0].update(prerequisites=["quest.record"]), "circular_quests"),
    (lambda d: d["skills"][0].update(prerequisites=["skill.repair"]) or d["skills"][1].update(prerequisites=["skill.practice"]), "circular_skills"),
    (lambda d: d["quests"][2]["objectives"][0].update(count=99), "impossible_objective"),
    (lambda d: d["locations"][1].update(locked_by=[{"kind": "quest_done", "target": "quest.record"}]), "unreachable_quest"),
    (lambda d: d["locations"][0].update(locked_by=[{"kind": "quest_done", "target": "quest.final"}]), "inaccessible_area"),
    (lambda d: d["enemies"][0].update(resistances={"damage.main": 100}), "unkillable_enemy"),
    (lambda d: d["enemies"][0].update(ability_ids=["ability.mend"]), "zero_damage_loop"),
    (lambda d: d["abilities"][0].update(cost={"resource.energy": 99}), "zero_damage_loop"),
    (lambda d: d["locations"][1].update(x=70), "invalid_topology"),
    (lambda d: d["dialogues"][0]["nodes"][0]["choices"][0].update(next_node_id="node.missing"), "malformed_dialogue"),
    (lambda d: d["dialogues"][0]["nodes"][0]["choices"][1].update(actions=[{"kind": "gold", "amount": 100}]), "repeatable_dialogue_reward"),
    (lambda d: d["crafting"][0].update(outputs={"item.relic": 20}), "impossible_economy"),
    (lambda d: d["items"][0].update(slot_id="slot.missing"), "invalid_reference"),
    (lambda d: d["player"].update(equipment_slots=["slot.body"]), "invalid_equipment"),
    (lambda d: d["progression"][0].update(unlocks={"tomorrow": ["ability.mend"]}), "broken_progression"),
    (lambda d: d["encounters"][1].update(conditions=[{"kind": "quest_done", "target": "quest.record"}]), "unreachable_quest"),
    (lambda d: d["assets"][0].update(path="../private.png", sha256="a" * 64), "invalid_asset"),
    (lambda d: d["abilities"][0]["effects"][0].update(amount=0), "ineffective_ability"),
    (lambda d: d["player"]["visual"].update(asset_id="asset.missing"), "invalid_reference"),
])
def test_validator_rejects_broken_mechanics(fantasy_data, mutation, code):
    mutation(fantasy_data)
    spec = RealmSpec.model_validate(fantasy_data)
    assert code in {i.code for i in validate_realm(spec)}
    with pytest.raises(InvalidRealm):
        RealmPackage(spec)


def test_package_files_are_validated_before_play(spec, tmp_path):
    package = RealmPackage(spec)
    path = package.write(tmp_path / "realm")
    loaded = RealmPackage.load(path)
    assert loaded.spec == spec
    assert loaded.digest == package.digest
    assert not list(tmp_path.glob(".realm-*"))
    with pytest.raises(FileExistsError):
        package.write(path)
    data = json.loads((path / "realm.json").read_text())
    data["player"]["name"] += " changed"
    (path / "realm.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="manifest"):
        RealmPackage.load(path)


def test_asset_manifest_requires_exact_bytes(fantasy_data, tmp_path):
    content = b"an existing asset fixture"
    import hashlib
    fantasy_data["assets"][0].update(provider="existing", path="assets/player.dat", sha256=hashlib.sha256(content).hexdigest())
    spec = RealmSpec.model_validate(fantasy_data)
    source = tmp_path / "source" / "assets"
    source.mkdir(parents=True)
    (source / "player.dat").write_bytes(content)
    package = RealmPackage(spec)
    with pytest.raises(ValueError, match="source"):
        package.write(tmp_path / "missing")
    assert not (tmp_path / "missing").exists()
    path = package.write(tmp_path / "present", source.parent)
    RealmPackage.load(path)
    (path / "assets/player.dat").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="corrupted"):
        RealmPackage.load(path)


def test_repairs_only_remove_optional_broken_art(fantasy_data):
    fantasy_data["player"]["visual"]["asset_id"] = "asset.absent"
    spec = RealmSpec.model_validate(fantasy_data)
    fixed, changes = repair_safe(spec)
    require_valid(fixed)
    assert changes and fixed.player.visual.asset_id is None
    assert fixed.player.name == spec.player.name
    assert spec.player.visual.asset_id == "asset.absent"


def test_adaptation_policy_defaults_to_original_and_requires_rights():
    assert AdaptationPolicy().mode == "original_inspiration"
    with pytest.raises(ValidationError):
        AdaptationPolicy(mode="licensed_adaptation")
    with pytest.raises(ValidationError):
        AdaptationPolicy(allow_source_names=True)


def test_generated_maps_preserve_reachable_content_and_seed(spec):
    a, b = build_maps(spec), build_maps(spec)
    assert a == b
    for m in a.values():
        reachable = m.reachable()
        assert reachable
        for eid, xy in m.points.items():
            if eid == "boss" or eid.startswith("location."):
                assert tuple(xy) in reachable
    changed = spec.model_copy(deep=True)
    changed.metadata.seed += 1
    assert build_maps(changed) != a


def test_fixture_players_are_distinct():
    specs = [RealmSpec.model_validate_json(p.read_bytes()) for p in sorted(Path("fixtures").glob("*.json"))]
    assert len({s.player.archetype for s in specs}) == 3
    assert len({s.resources[1].name for s in specs}) == 3
    assert len({s.abilities[1].effects[0].kind for s in specs}) == 2
    assert len({s.player.movement for s in specs}) == 2


def test_schema_file_matches_models():
    assert json.loads(Path("schemas/realm_spec_v1.schema.json").read_text()) == RealmSpec.model_json_schema()


def test_location_overlap_and_unfundable_payment_rejected(fantasy_data):
    fantasy_data["locations"][1]["x"] = fantasy_data["locations"][0]["x"]
    fantasy_data["locations"][1]["y"] = fantasy_data["locations"][0]["y"]
    fantasy_data["quests"][0]["objectives"] = [{"kind": "pay", "target_id": "location.home", "count": 1000000}]
    for encounter in fantasy_data["encounters"]:
        encounter["respawn_turns"] = 0
    codes = {i.code for i in validate_realm(RealmSpec.model_validate(fantasy_data))}
    assert {"overlapping_locations", "impossible_economy"} <= codes


def test_package_snapshot_and_optional_v1_fields_preserve_identity(spec, tmp_path):
    import hashlib
    package = RealmPackage(spec)
    original_name = package.spec.player.name
    digest = package.digest
    spec.player.name = "An external mutable edit"
    copy = package.spec; copy.player.name = "A temporary working copy"
    assert package.spec.player.name == original_name and package.digest == digest
    path = package.write(tmp_path / "v1")
    data = json.loads((path / "realm.json").read_text())
    data["player"].pop("passives")
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    (path / "realm.json").write_bytes(raw)
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["spec_sha256"] = hashlib.sha256(raw).hexdigest()
    (path / "manifest.json").write_text(json.dumps(manifest))
    restored = RealmPackage.load(path)
    assert restored.spec.player.passives == []
    assert restored.digest == manifest["spec_sha256"]
    copied = restored.write(tmp_path / "copy")
    assert (copied / "realm.json").read_bytes() == raw
    assert RealmPackage.load(copied).digest == restored.digest
