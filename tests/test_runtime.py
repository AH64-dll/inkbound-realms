import json
import os
import subprocess
from collections import deque
from pathlib import Path

import pytest

from inkbound.realm.models import RealmSpec
from inkbound.realm.package import RealmPackage
from inkbound.runtime.engine import Engine


def test_one_turn_restraint_blocks_reply_and_player_move(spec):
    data = spec.model_dump(mode="json")
    data["status_effects"][0]["skip_turn"] = True
    e = Engine(RealmPackage(RealmSpec.model_validate(data)))
    sid = e.spec.status_effects[0].id
    enemy = next(iter(e.state.actors.values()))
    enemy.map_id = e.player.map_id
    enemy.x, enemy.y = e.player.x + 1, e.player.y
    enemy.statuses[sid] = 1
    before = enemy.model_dump()
    e.tick()
    assert sid not in enemy.statuses
    assert (enemy.x, enemy.y, enemy.telegraph) == (before["x"], before["y"], before["telegraph"])
    e.player.statuses[sid] = 1
    position = (e.player.x, e.player.y)
    turn = e.state.turn
    assert e.move(0, 1)
    assert (e.player.x, e.player.y) == position
    assert e.state.turn == turn + 1 and sid not in e.player.statuses


def test_escort_is_a_saved_living_companion_and_requires_safe_arrival(spec, tmp_path):
    data = spec.model_dump(mode="json")
    quest = dict(data["quests"][0])
    quest.update(id="quest.escort", prerequisites=[], discovered=True,
                 objectives=[{"kind": "escort", "target_id": "npc.guide", "destination_id": "location.refuge"}])
    data["quests"].append(quest)
    e = Engine(RealmPackage(RealmSpec.model_validate(data)))
    visit_guide(e)
    companion = e.state.actors["companion:npc.guide"]
    assert companion.friendly and e.alive(companion)
    path = tmp_path / "escort.json"
    e.save(path); e = Engine.load(e.package, path)
    companion = e.state.actors["companion:npc.guide"]
    companion.resources[e.health_id] = 0
    e.leave()
    destination = e.current_map.points["location.refuge"]
    e.player.x, e.player.y = destination
    e.visit("location.refuge"); e._companions_follow()
    assert not e.state.flags.get("escort.npc.guide")
    # A fallen escort can recover at a safe inn, then resume the journey.
    home = e.current_map.points["location.home"]
    e.player.x, e.player.y = home
    assert e.enter("location.home") and e.rest()
    assert e.alive(companion)
    e.leave(); e.player.x, e.player.y = destination
    e._companions_follow()
    assert e.state.flags["escort.npc.guide"] == 1
    assert "companion:npc.guide" not in e.state.actors
    visit_guide(e)
    assert "quest.escort" in e.state.quests_done


def navigate(engine, destination):
    """Play legal moves along a route, resolving the threats that interrupt it."""
    for _ in range(1500):
        if not engine.alive(engine.player):
            raise AssertionError("Campaign player fell")
        if [engine.player.x, engine.player.y] == list(destination):
            return
        start = (engine.player.x, engine.player.y)
        queue = deque([start]); came = {start: None}
        while queue and tuple(destination) not in came:
            x, y = queue.popleft()
            for xy in [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]:
                if xy not in came and engine.current_map.walkable(*xy):
                    came[xy] = (x, y); queue.append(xy)
        assert tuple(destination) in came
        next_xy = tuple(destination)
        while came[next_xy] != start:
            next_xy = came[next_xy]
        blocking = [a for a in engine.threats() if (a.x, a.y) == next_xy]
        if engine.player.resources[engine.health_id] < 25 and engine.state.inventory.get("item.potion", 0):
            engine.use_item("item.potion")
        elif blocking:
            assert engine.use_ability(engine.rules.default_ability_id, blocking[0].id)
        else:
            assert engine.move(next_xy[0] - start[0], next_xy[1] - start[1])
    raise AssertionError("Navigation did not converge")


def visit_guide(engine):
    home = engine.index["location.home"]
    if engine.player.map_id != home.id:
        assert engine.player.map_id == home.region_id
        navigate(engine, engine.current_map.points[home.id])
        assert engine.enter(home.id)
    navigate(engine, engine.state.npc_positions["npc.guide"])
    assert engine.talk("npc.guide")
    engine.close_dialogue()


def resolve_delve(engine, loc_id):
    loc = engine.index[loc_id]
    navigate(engine, engine.current_map.points[loc_id])
    assert engine.enter(loc_id)
    for actor_id in [a.id for a in engine.threats()]:
        for _ in range(200):
            actor = engine.state.actors[actor_id]
            if actor.defeated:
                break
            if engine.player.resources[engine.health_id] < 25:
                if engine.state.inventory.get("item.potion", 0):
                    engine.use_item("item.potion"); continue
                if "ability.mend" in engine.known_abilities() and engine.player.resources.get("resource.energy", 0) >= 4:
                    engine.use_ability("ability.mend"); continue
            if engine.distance(engine.player, actor) <= 1:
                engine.use_ability(engine.rules.default_ability_id, actor.id)
            elif (engine.index["ability.special"].target == "enemy"
                  and engine.distance(engine.player, actor) <= engine.index["ability.special"].range
                  and engine.line_clear(engine.player, actor)
                  and engine.player.cooldowns.get("ability.special", 0) <= engine.state.turn
                  and engine.player.resources.get("resource.energy", 0) >= 3):
                engine.use_ability("ability.special", actor.id)
            else:
                # Move toward its current tile; hostile actors are obstacles handled by navigate.
                navigate(engine, [actor.x, actor.y])
        assert actor.defeated
    assert engine.leave()


def test_three_complete_fixture_campaigns(spec, tmp_path):
    engine = Engine(RealmPackage(spec))
    assert engine.craft("recipe.recovery")
    visit_guide(engine)
    assert "quest.salvage" in engine.state.quests_done
    assert engine.heal()
    engine.leave()
    # Story gate really holds before the record is recovered.
    assert "location.final" not in engine.state.unlocked
    resolve_delve(engine, "location.delve")
    assert engine.item_count("item.relic") == 1
    visit_guide(engine)
    assert "quest.survey" in engine.state.quests_done
    assert "quest.record" in engine.state.quests_done
    assert "location.final" in engine.state.unlocked
    assert engine.item_count("item.relic") == 0
    engine.heal(); engine.rest(); engine.leave()
    resolve_delve(engine, "location.final")
    visit_guide(engine)
    assert "quest.final" in engine.state.quests_done
    engine.tick(enemies=False)
    assert engine.state.flags["flag.victory"] == 1
    assert engine.state.level >= 3
    assert engine.state.standing["faction.commons"] >= 15
    engine.save(tmp_path / "campaign.json")
    restored = Engine.load(engine.package, tmp_path / "campaign.json")
    assert restored.state == engine.state
    # Victory leaves a functioning explorable world.
    assert restored.leave()
    assert restored.alive(restored.player)


def test_save_resume_preserves_next_random_outcomes(spec, tmp_path):
    a = Engine(RealmPackage(spec))
    a.craft("recipe.recovery"); a.tick(enemies=False)
    a.save(tmp_path / "save.json")
    b = Engine.load(a.package, tmp_path / "save.json")
    for _ in range(12):
        a.tick(); b.tick()
        assert a.rng().randrange(1000000) == b.rng().randrange(1000000)
    assert a.state == b.state


def test_determinism_across_python_processes(tmp_path):
    script = """
import hashlib
from pathlib import Path
from inkbound.realm.models import RealmSpec
from inkbound.realm.package import RealmPackage, canonical
from inkbound.runtime.engine import Engine
s=RealmSpec.model_validate_json(Path('fixtures/science_fiction.json').read_bytes())
e=Engine(RealmPackage(s)); e.craft('recipe.recovery')
for _ in range(12): e.tick()
print(hashlib.sha256(canonical(e.state.model_dump(mode='json'))).hexdigest())
"""
    results = [subprocess.check_output([os.sys.executable, "-c", script], env={**os.environ, "PYTHONHASHSEED": str(seed)}, text=True).strip() for seed in (1, 987654)]
    assert results[0] == results[1]


def test_invalid_or_wrong_revision_save_rejected(spec, tmp_path):
    e = Engine(RealmPackage(spec)); path = tmp_path / "state.json"; e.save(path)
    other = spec.model_copy(deep=True); other.metadata.revision += 1
    with pytest.raises(ValueError, match="revision"):
        Engine.load(RealmPackage(other), path)
    data = json.loads(path.read_text()); data["player"]["x"] = -100
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="location"):
        Engine.load(e.package, path)


def test_crafting_is_transactional_and_trains(spec):
    e = Engine(RealmPackage(spec))
    assert e.craft("recipe.recovery")
    before = e.state.model_dump()
    assert not e.craft("recipe.recovery")
    # A failure may add a helpful message, but cannot spend inventory/gold/turns.
    after = e.state.model_dump()
    for key in ("inventory", "gold", "turn", "crafted", "skills"):
        assert after[key] == before[key]


def controlled_combat(spec):
    e = Engine(RealmPackage(spec))
    e.state.actors.clear()
    e.enter("location.home"); e.close_dialogue()
    # Two neighboring walkable tiles in the settlement are a controlled encounter.
    for xy in sorted(e.current_map.reachable()):
        if e.current_map.walkable(xy[0] + 1, xy[1]):
            e.player.x, e.player.y = xy
            enemy = e._actor(e.index["enemy.guard"], "test.guard", e.player.map_id, xy[0] + 1, xy[1])
            e.state.actors[enemy.id] = enemy
            break
    return e, enemy


def test_guard_mitigates_one_reply_and_typed_shield_applies_once(spec):
    e, foe = controlled_combat(spec)
    hp = e.player.resources[e.health_id]
    e.player.guard = True; e.player.shield = 2
    dealt = e.damage(foe, e.player, 20, "damage.main")
    # Body armor + base armor = 2; 18 // 4 = 4; shield absorbs 2.
    assert dealt == 2
    assert e.player.resources[e.health_id] == hp - 2
    assert e.player.shield == 0 and not e.player.guard


def test_nonviolent_resolution_advances_quarry_and_loot(spec):
    e, foe = controlled_combat(spec)
    assert e.use_ability("ability.negotiate", foe.id)
    assert foe.defeated
    assert e.state.kills["enemy.guard"] == 1
    assert e.state.inventory["item.material"] == 4
    before = e.state.gold
    e.defeat(foe, True)
    assert e.state.gold == before


def test_abilities_spend_resources_and_reject_out_of_range(spec):
    e, foe = controlled_combat(spec)
    if e.index["ability.special"].target == "self":
        assert e.use_ability("ability.special")
        assert e.player.shield > 0
    else:
        foe.x += 10
        before = dict(e.player.resources)
        assert not e.use_ability("ability.special", foe.id)
        assert e.player.resources == before


def test_dialogue_choices_and_repeat_turnins(spec):
    e = Engine(RealmPackage(spec)); visit_guide(e)
    assert e.talk("npc.guide")
    assert e.choose("choice.why")
    assert e.dialogue_node().id == "node.stakes"
    assert e.choose("choice.return")
    assert e.choose("choice.leave")
    assert not e.state.active_dialogue_id
    before = e.state.gold
    for _ in range(5):
        e.turn_in("npc.guide")
    assert e.state.gold == before


def test_runtime_has_no_provider_imports():
    for path in Path("inkbound/runtime").glob("*.py"):
        text = path.read_text()
        assert "inkbound.authoring" not in text
