"""Story plotter: one main tale per world, woven from its own annals.

Four archetypes across 4 acts (8 beats each), dealt by what the world holds:
the Return (an heir), the Sundered Crown (a faction war), the Waking Dark
(the dead stir), the Wyrm Verses (drakes migrate). Beats are ordinary quests
(deliver/explore/hunt/bounty/escort/defend/rescue/choice/relic/finale) with
the rule that makes them a STORY: one active beat at a time, named givers,
a villain that answers every page, and a choice along the way. Victory ends
the tale, not the game.
"""
from __future__ import annotations

import random


def _pick_villain(world) -> str:
    # the most wronged soul inherits the dark: slain/betrayed weigh double
    try:
        scores: dict[str, int] = {}
        for r in (getattr(world, "rivalries", []) or []):
            wgt = 2 if r.get("verb") in ("slay", "betray") else 1
            scores[r["b"]] = scores.get(r["b"], 0) + wgt
        if scores:
            return f"Heir of {max(scores, key=lambda k: scores[k])}"
    except Exception:
        pass
    deaths = [e for e in world.history if e.get("kind") == "death" and e.get("people")]
    if deaths:
        d = max(deaths, key=lambda e: e.get("year", 0))
        return f"Heir of {d['people'][0]}"
    if world.history:
        return "The Hollow King"
    return "The Hollow King"


def _giver(world, rng: random.Random, city_name: str = "") -> str:
    """A named mouth for the tale (never the Annals twice running)."""
    pool = [c.name for c in world.characters if c.role != "bandit"
            and (not city_name or c.city == city_name)]
    if not pool:
        pool = [c.name for c in world.characters if c.role != "bandit"]
    if not pool:
        return "The Annals"
    return rng.choice(pool)


def _capital(world):
    fh = (world.factions or [None])[0]
    if fh and fh.cities:
        return fh.cities[0]
    return world.cities[0].name if world.cities else ""


def _foe_capital(world):
    fh = (world.factions or [None])[0]
    if fh and fh.at_war and world.factions:
        foe = next((f for f in world.factions if f.id in fh.at_war), None)
        if foe is not None and foe.cities:
            return foe.cities[0]
    return ""


def _far_dungeon(world):
    dens = [s for s in world.sites if s.kind == "dungeon"]
    if not dens:
        return ""
    cx, cy = world.width // 2, world.height // 2
    return max(dens, key=lambda s: abs(s.x - cx) + abs(s.y - cy)).name


def _bandit(world, rng: random.Random) -> str:
    bandits = [c.name for c in world.characters if c.role == "bandit"]
    return rng.choice(bandits) if bandits else "the Red Hood"


def _lair(world, city_name: str) -> str:
    home = next((c for c in world.cities if c.name == city_name), None)
    dens = [s for s in world.sites if s.kind == "dungeon"]
    pool = dens or list(world.sites)
    if home and pool:
        return min(pool, key=lambda d: abs(d.x - home.x) + abs(d.y - home.y)).name
    return pool[0].name if pool else ""


def _other_city(world, rng: random.Random, not_in: str = "") -> str:
    others = [c.name for c in world.cities if c.name != not_in]
    return rng.choice(others) if others else not_in


def _build_return(world, rng: random.Random) -> tuple[str, str, list, dict]:
    """The heir comes home: warn, ashes, cull, hold, heirloom, heir, choice, tyrant."""
    from .quests import Quest
    villain = _pick_villain(world)
    capital = _capital(world)
    fh = (world.factions or [None])[0]
    foe_faction = ""
    if fh and fh.at_war and world.factions:
        foe = next((f for f in world.factions if f.id in fh.at_war), None)
        foe_faction = foe.name if foe else ""
    ruins = [s for s in world.sites if s.kind == "ruin"]
    dens = [s for s in world.sites if s.kind == "dungeon"]
    rsite = rng.choice(ruins).name if ruins else (dens[0].name if dens else "")
    relics = [a for a in world.artifacts if not a.get("claimed")][:1]
    heir = next((c.name for c in world.characters if c.role not in ("bandit",)), "the heir")
    blade = _bandit(world, rng)
    finale_site = _far_dungeon(world)
    title = f"{villain}'s Return"
    beats = [
        Quest(id="plot-0-warning", kind="deliver", act=1,
              title=f"Warn {capital}" if capital else "Whispers on the Wind",
              giver=_giver(world, rng, capital), target_city=capital,
              flavor=f"Old hate stirs: {villain} gathers blades. Carry the warning to {capital}.",
              reward_gold=15, reward_xp=30),
        Quest(id="plot-1-ashes", kind="explore", act=1,
              title=f"Walk the Ashes of {rsite}" if rsite else "Read the Border Wilds",
              giver=_giver(world, rng), target_site=rsite,
              flavor=f"{villain} was forged in that old fall. Stand where it burned; learn.",
              reward_gold=12, reward_xp=35),
        Quest(id="plot-2-cull", kind="hunt", act=2,
              title=f"Bleed the {foe_faction or 'Usurper'} Raiders",
              giver=_giver(world, rng, capital), target_enemy=foe_faction or "raiders", amount=4,
              flavor=f"{villain}'s vanguard raids in {foe_faction or 'stolen'} colors. Cull 4.",
              reward_gold=20, reward_xp=45),
        Quest(id="plot-3-hold", kind="defend", act=2,
              title=f"Hold {capital}" if capital else "Hold the Line",
              giver=_giver(world, rng, capital), target_city=capital, amount=3,
              flavor=f"{villain} tests the gates. Bleed 3 foes within the leagues of {capital}.",
              reward_gold=20, reward_xp=50),
    ]
    if relics:
        a = relics[0]
        beats.append(Quest(
            id="plot-4-heirloom", kind="relic", act=3,
            title=f"Reclaim {a['name']}",
            giver=_giver(world, rng), target_site=a.get("dungeon", ""),
            flavor=f"The old {a['name']} sleeps in {a.get('dungeon', 'the dark')}. Wake it.",
            reward_gold=10, reward_xp=55))
    else:
        beats.append(Quest(
            id="plot-4-heirloom", kind="explore", act=3,
            title=f"Plunder {rsite}" if rsite else "Plunder the Old Vaults",
            giver=_giver(world, rng), target_site=rsite,
            flavor="Power sleeps below. Take what the dead no longer need.",
            reward_gold=10, reward_xp=55))
    far = _other_city(world, rng, capital)
    beats.append(Quest(
        id="plot-5-heir", kind="escort", act=3,
        title=f"Guide {heir} to {far}" if far else f"Guide {heir}",
        giver=_giver(world, rng, capital), target_city=far, companion=heir,
        flavor=f"{heir} carries the blood that can gainsay {villain}. See them safe to {far}.",
        reward_gold=18, reward_xp=60))
    beats.append(Quest(
        id="plot-6-blade", kind="choice", act=4,
        title=f"Decide {blade}'s Fate",
        giver=_giver(world, rng), target_enemy=blade, target_site=_lair(world, capital),
        flavor=f"{blade} rides for {villain}. Slay them, charm them free, or take their kneeling oath.",
        reward_gold=22, reward_xp=65))
    beats.append(Quest(
        id="plot-7-tyrant", kind="finale", act=4,
        title=f"End {villain}",
        giver=_giver(world, rng, capital), target_enemy=villain, target_site=finale_site,
        flavor=(f"It ends where power sleeps: {finale_site}. Go down, and end it."
                if finale_site else f"Find {villain} in the wilds, and end it."),
        reward_gold=100, reward_xp=300))
    return title, villain, finale_site, beats, \
        {"acts": ["Embers", "The Vanguard", "Blood Debts", "The Return"]}


def _build_crown(world, rng: random.Random) -> tuple[str, str, list, dict]:
    """Two powers, one crown: terms, blades, a held border, the piece, an
    envoy, a parley with three roads, the breaking, the champion."""
    from .quests import Quest
    fh = (world.factions or [None])[0]
    foe = None
    if fh and fh.at_war and world.factions:
        foe = next((f for f in world.factions if f.id in fh.at_war), None)
    mine = _capital(world)
    theirs = _foe_capital(world) or _other_city(world, rng, mine)
    foe_name = foe.name if foe else "the Usurper"
    villain = f"Champion of {foe_name}"
    relics = [a for a in world.artifacts if not a.get("claimed")][:1]
    blade = _bandit(world, rng)
    envoy = next((c.name for c in world.characters if c.role not in ("bandit",)), "the envoy")
    far = _other_city(world, rng, mine)
    finale_site = _far_dungeon(world)
    title = f"The Sundered Crown of {mine}" if mine else "The Sundered Crown"
    beats = [
        Quest(id="plot-0-terms", kind="deliver", act=1,
              title=f"Carry Terms to {theirs}" if theirs else "Carry the Terms",
              giver=_giver(world, rng, mine), target_city=theirs,
              flavor=f"War eats both granaries. Carry {mine or 'our'} terms to {theirs}.",
              reward_gold=15, reward_xp=30),
        Quest(id="plot-1-blade", kind="bounty", act=1,
              title=f"Bounty: {blade}",
              giver=_giver(world, rng, mine), target_enemy=blade, target_site=_lair(world, mine),
              flavor=f"{blade} cuts peacemakers down. End them{' in ' + _lair(world, mine) if _lair(world, mine) else ''}.",
              reward_gold=20, reward_xp=40),
        Quest(id="plot-2-border", kind="defend", act=2,
              title=f"Hold {mine}" if mine else "Hold the Border",
              giver=_giver(world, rng, mine), target_city=mine, amount=3,
              flavor=f"{foe_name} tests the border. Bleed 3 foes within the leagues of {mine}.",
              reward_gold=20, reward_xp=50),
    ]
    if relics:
        a = relics[0]
        beats.append(Quest(
            id="plot-3-piece", kind="relic", act=2,
            title=f"Reclaim {a['name']}",
            giver=_giver(world, rng, mine), target_site=a.get("dungeon", ""),
            flavor=f"Both powers claim {a['name']}. Take it first, from {a.get('dungeon', 'the dark')}.",
            reward_gold=10, reward_xp=55))
    else:
        beats.append(Quest(
            id="plot-3-piece", kind="tribute", act=2,
            title=f"War Chest for {mine}" if mine else "Fill the War Chest",
            giver=_giver(world, rng, mine), target_city=mine, amount=60,
            flavor=f"Wars eat gold. Lay 60g at {mine}.",
            reward_gold=8, reward_xp=55))
    beats.append(Quest(
        id="plot-4-envoy", kind="escort", act=3,
        title=f"Guide {envoy} to {far}" if far else f"Guide {envoy}",
        giver=_giver(world, rng, mine), target_city=far, companion=envoy,
        flavor=f"The parley needs a voice {foe_name} trusts. Walk {envoy} to {far}.",
        reward_gold=18, reward_xp=60))
    beats.append(Quest(
        id="plot-5-parley", kind="choice", act=3,
        title=f"The Parley: {blade}",
        giver=_giver(world, rng, mine), target_enemy=blade, target_site=_lair(world, theirs),
        flavor=f"{blade} speaks for {foe_name} at the parley stones. Slay, spare, or swear them.",
        reward_gold=22, reward_xp=65))
    beats.append(Quest(
        id="plot-6-break", kind="hunt", act=4,
        title=f"Break the {foe_name} Host",
        giver=_giver(world, rng, mine), target_enemy=foe.id if foe else "raiders", amount=5,
        flavor=f"The parley is dust. Bleed the {foe_name} host — 5 of them.",
        reward_gold=24, reward_xp=70))
    beats.append(Quest(
        id="plot-7-champion", kind="finale", act=4,
        title=f"End {villain}",
        giver=_giver(world, rng, mine), target_enemy=villain, target_site=finale_site,
        flavor=(f"{villain} holes in {finale_site}. Go down, and end the war's edge."
                if finale_site else f"Find {villain}, and end the war's edge."),
        reward_gold=100, reward_xp=300))
    return title, villain, finale_site, beats, \
        {"acts": ["Terms of War", "The Border Bleeds", "The Parley", "The Breaking"]}


def _build_dark(world, rng: random.Random) -> tuple[str, str, list, dict]:
    """The dead stir: barrows, blades, shrines, a farmstead, a priest, a vicar,
    the host, the Barrow-Lord."""
    from .quests import Quest
    deaths = [e for e in world.history if e.get("kind") == "death" and e.get("people")]
    villain = f"the Barrow-Lord, Heir of {deaths[-1]['people'][0]}" if deaths else "the Pale King"
    ruins = [s for s in world.sites if s.kind == "ruin"]
    dens = [s for s in world.sites if s.kind == "dungeon"]
    barrow = rng.choice(ruins).name if ruins else (dens[0].name if dens else "")
    shrines = [s for s in world.sites if s.kind == "shrine"]
    capital = _capital(world)
    blade = _bandit(world, rng)
    priest = next((c.name for c in world.characters if c.role not in ("bandit",)), "the last priest")
    far = _other_city(world, rng, capital)
    finale_site = _far_dungeon(world)
    title = f"The Waking Dark of {barrow}" if barrow else "The Waking Dark"
    beats = [
        Quest(id="plot-0-barrow", kind="explore", act=1,
              title=f"Walk {barrow}" if barrow else "Walk the Cold Stones",
              giver=_giver(world, rng), target_site=barrow,
              flavor=f"The dead do not rest in {barrow or 'the cold stones'}. Stand there; learn.",
              reward_gold=12, reward_xp=35),
        Quest(id="plot-1-blade", kind="bounty", act=1,
              title=f"Bounty: {blade}",
              giver=_giver(world, rng, capital), target_enemy=blade, target_site=_lair(world, capital),
              flavor=f"{blade} feeds the barrows with travelers. End them.",
              reward_gold=20, reward_xp=40),
    ]
    if len(shrines) >= 2:
        beats.append(Quest(
            id="plot-2-lights", kind="pilgrimage", act=2,
            title="Pilgrimage of 2 Lights",
            giver=_giver(world, rng), amount=2,
            flavor="The old lights hold the dark back. Kneel at 2 shrines — each stone once.",
            reward_gold=15, reward_xp=50))
    else:
        beats.append(Quest(
            id="plot-2-lights", kind="hunt", act=2,
            title="Cull the Risen",
            giver=_giver(world, rng), target_enemy="undead", amount=4,
            flavor="No lights to kneel at. Send the risen back instead — 4 of them.",
            reward_gold=18, reward_xp=50))
    beats.append(Quest(
        id="plot-3-stead", kind="defend", act=2,
        title=f"Hold {capital}" if capital else "Hold the Steading",
        giver=_giver(world, rng, capital), target_city=capital, amount=3,
        flavor=f"The dead shamble for {capital}. Bleed 3 foes within its leagues.",
        reward_gold=20, reward_xp=50))
    beats.append(Quest(
        id="plot-4-priest", kind="escort", act=3,
        title=f"Guide {priest} to {far}" if far else f"Guide {priest}",
        giver=_giver(world, rng, capital), target_city=far, companion=priest,
        flavor=f"{priest} knows the binding words. Walk them living to {far}.",
        reward_gold=18, reward_xp=60))
    beats.append(Quest(
        id="plot-5-vicar", kind="choice", act=3,
        title="Decide the Pale Vicar's Fate",
        giver=_giver(world, rng), target_enemy=blade, target_site=_lair(world, capital),
        flavor="The Vicar serves the Barrow-Lord willingly — or so it claims. Slay, spare, or swear it.",
        reward_gold=22, reward_xp=65))
    beats.append(Quest(
        id="plot-6-host", kind="hunt", act=4,
        title="Cull the Risen Host",
        giver=_giver(world, rng), target_enemy="undead", amount=5,
        flavor="The host masses in the cold. Send 5 back to the earth.",
        reward_gold=24, reward_xp=70))
    beats.append(Quest(
        id="plot-7-lord", kind="finale", act=4,
        title=f"End {villain}",
        giver=_giver(world, rng, capital), target_enemy=villain, target_site=finale_site,
        flavor=(f"{villain} dreams in {finale_site}. Go down, and wake it last."
                if finale_site else f"Find {villain}, and wake it last."),
        reward_gold=100, reward_xp=300))
    return title, villain, finale_site, beats, \
        {"acts": ["Cold Stones", "Lights Against Dark", "The Binding", "The Barrow-Lord"]}


def _build_wyrm(world, rng: random.Random) -> tuple[str, str, list, dict]:
    """Drakes migrate down: lairs, culls, a herald, a rookery, a burner, a
    broodmother with three roads, the last flight."""
    from .quests import Quest
    villain = "the Broodmother"
    dens = [s for s in world.sites if s.kind == "dungeon"]
    lair = rng.choice(dens).name if dens else ""
    capital = _capital(world)
    blade = _bandit(world, rng)
    burner = next((c.name for c in world.characters if c.role not in ("bandit",)), "the burner")
    far = _other_city(world, rng, capital)
    finale_site = _far_dungeon(world)
    title = f"The Wyrm Verses over {lair}" if lair else "The Wyrm Verses"
    beats = [
        Quest(id="plot-0-lair", kind="explore", act=1,
              title=f"Find the Wyrm Lair {lair}" if lair else "Find the Wyrm Lair",
              giver=_giver(world, rng), target_site=lair,
              flavor="Smoke on the high wind. Find where the wyrms den.",
              reward_gold=12, reward_xp=35),
        Quest(id="plot-1-cull", kind="hunt", act=1,
              title="Cull the Drakes",
              giver=_giver(world, rng), target_enemy="drake", amount=2,
              flavor="The young ones hunt livestock and herders. Cull 2 drakes.",
              reward_gold=20, reward_xp=40),
        Quest(id="plot-2-herald", kind="bounty", act=2,
              title=f"Bounty: {blade}",
              giver=_giver(world, rng, capital), target_enemy=blade, target_site=_lair(world, capital),
              flavor=f"{blade} sells wyrm-fire to the highest bidder. End them.",
              reward_gold=20, reward_xp=50),
        Quest(id="plot-3-rook", kind="defend", act=2,
              title=f"Hold {capital}" if capital else "Hold the Rookery Town",
              giver=_giver(world, rng, capital), target_city=capital, amount=3,
              flavor=f"The flock circles {capital}. Bleed 3 foes within its leagues.",
              reward_gold=20, reward_xp=50),
        Quest(id="plot-4-burner", kind="escort", act=3,
              title=f"Guide {burner} to {far}" if far else f"Guide {burner}",
              giver=_giver(world, rng, capital), target_city=far, companion=burner,
              flavor=f"{burner} knows oil and flame. Walk them to {far} to ready the pyres.",
              reward_gold=18, reward_xp=60),
        Quest(id="plot-5-brood", kind="choice", act=3,
              title="Decide the Broodmother's Fate",
              giver=_giver(world, rng), target_enemy=blade, target_site=_lair(world, capital),
              flavor="The Broodmother's eldest speaks with a human mouth. Slay it, spare it, or swear it.",
              reward_gold=22, reward_xp=65),
        Quest(id="plot-6-flight", kind="hunt", act=4,
              title="Cull the Last Flight",
              giver=_giver(world, rng), target_enemy="drake", amount=4,
              flavor="The sky darkens. Cull 4 drakes before the pyres light.",
              reward_gold=24, reward_xp=70),
        Quest(id="plot-7-mother", kind="finale", act=4,
              title=f"End {villain}",
              giver=_giver(world, rng, capital), target_enemy=villain, target_site=finale_site,
              flavor=(f"{villain} nests in {finale_site}. Go down, and end the verses."
                      if finale_site else f"Find {villain}, and end the verses."),
              reward_gold=100, reward_xp=300),
    ]
    return title, villain, finale_site, beats, \
        {"acts": ["Smoke on the Wind", "Fire Sale", "The Pyres", "The Broodmother"]}


def _pick_archetype(world) -> str:
    """Deal by ingredients: crown wants war + relics, dark wants ruins,
    wyrm wants peaks, return always answers."""
    wars = [f for f in world.factions if f.at_war]
    relics = [a for a in world.artifacts if not a.get("claimed")]
    ruins = [s for s in world.sites if s.kind == "ruin"]
    deaths = [e for e in world.history if e.get("kind") in ("death", "fall", "sack")]
    peaks = False
    try:
        peaks = any("^" in row for row in world.grid)
    except Exception:
        pass
    if wars and len(relics) >= 2:
        return "crown"
    if len(ruins) >= 2 and len(deaths) >= 6:
        return "dark"
    if peaks and len(relics) < 2 and len(ruins) < 2:
        return "wyrm"
    if wars or len(relics) >= 2:
        return "crown" if wars else "return"
    if ruins:
        return "dark"
    return "return"


def weave_plot(world, rng: random.Random | None = None) -> dict:
    """Cast the realm's main tale. Idempotent-ish: call once per world."""
    rng = rng or random.Random(world.seed + 4242)
    arch = _pick_archetype(world)
    builders = {"return": _build_return, "crown": _build_crown,
                "dark": _build_dark, "wyrm": _build_wyrm}
    title, villain, finale_site, beats, extra = builders[arch](world, rng)
    return {"title": title, "villain": villain, "finale_site": finale_site,
            "archetype": arch,
            "beat_ids": [q.id for q in beats], "beats": [q.to_dict() for q in beats],
            "current": 0, "done": False, "acts": extra["acts"]}


def ensure_plot(world, rng: random.Random | None = None) -> dict:
    """Legacy saves (and fresh worlds that skipped it) get their tale."""
    plot = getattr(world, "plot", None) or {}
    if plot.get("beat_ids"):
        return plot
    plot = weave_plot(world, rng)
    world.plot = plot
    # unlock the opening beat immediately
    first = plot["beats"][0]
    from .quests import Quest
    if first["id"] not in {q.id for q in world.quests} | set(world.completed_quests):
        world.quests.append(Quest.from_dict(first))
    return plot


def current_beat(world) -> dict | None:
    plot = getattr(world, "plot", None) or {}
    if plot.get("done"):
        return None
    idx = plot.get("current", 0)
    beats = plot.get("beats", [])
    if 0 <= idx < len(beats):
        return beats[idx]
    return None


def _side_tales(state) -> int:
    return sum(1 for qid in (state.world.completed_quests or []) if not qid.startswith("plot-"))


def _villain_move(state, plot: dict) -> None:
    """Every turned page, the villain answers: annals, warbands, posters."""
    import random as _r
    w = state.world
    rng = _r.Random(w.seed + len(w.completed_quests) * 17)
    villain = plot.get("villain", "the foe")
    last = max([e.get("year", 0) for e in w.history] + [800])
    w.history.append({"year": last + 1, "kind": "omen",
                      "text": f"{villain} answers: blades muster in the dark.",
                      "place": "", "people": [villain]})
    w.history.sort(key=lambda e: (e.get("year", 0), e.get("kind", "")))
    w.history = w.history[-220:]
    if rng.random() < 0.5 and state.interior is None:
        bandits = [c for c in w.characters if c.role == "bandit"] or w.characters[:4]
        try:
            from .game import spawn_group
            theme = {"crown": "war", "dark": "dead", "wyrm": "wild"}.get(
                plot.get("archetype", "return"), "bandit")
            spawn_group(state, state.player.x, state.player.y, rng, bandits, theme,
                        level_scale=max(0, (state.player.level - 1) // 2))
        except Exception:
            pass


def _release_plot(state) -> bool:
    """Gated pages turn when the realm has had its own tales first."""
    from .quests import Quest
    w = state.world
    plot = getattr(w, "plot", None) or {}
    if plot.get("done") or not plot.get("archetype"):
        return False
    held = plot.get("held")
    if not held:
        return False
    need = 4 if held.get("act", 3) >= 4 else 2
    if _side_tales(state) < need:
        return False
    nxt = Quest.from_dict(held)
    if nxt.id not in {q.id for q in w.quests} and nxt.id not in w.completed_quests:
        w.quests.append(nxt)
    plot["held"] = None
    state.log(f"+ The tale turns: {nxt.title} (Act {nxt.act}/{len(plot.get('acts', [])) or 4}).")
    _villain_move(state, plot)
    w.plot = plot
    return True


def advance_plot(state, completed_id: str) -> bool:
    """A finished beat turns the page (later acts wait for side tales).
    Returns True on advancement."""
    from .quests import Quest
    w = state.world
    plot = getattr(w, "plot", None) or {}
    if plot.get("done"):
        return False
    beats = plot.get("beats", [])
    idx = plot.get("current", 0)
    if not (0 <= idx < len(beats)) or beats[idx]["id"] != completed_id:
        if plot.get("held"):
            return _release_plot(state)
        return False
    if idx + 1 < len(beats):
        plot["current"] = idx + 1
        nxt = beats[idx + 1]
        gated = bool(plot.get("archetype")) and nxt.get("act", 1) >= 3
        need = 4 if nxt.get("act", 1) >= 4 else 2
        if gated and _side_tales(state) < need:
            plot["held"] = nxt
            state.log(f"= The tale waits: finish {need - _side_tales(state)} more "
                      f"tale(s) and it will turn.")
        else:
            q = Quest.from_dict(nxt)
            if q.id not in {x.id for x in w.quests} and q.id not in w.completed_quests:
                w.quests.append(q)
            acts = len(plot.get("acts", [])) or 4
            state.log(f"+ The tale turns: {q.title} (Act {q.act}/{acts}).")
        if plot.get("archetype"):
            _villain_move(state, plot)
    else:
        plot["done"] = True
        state.log(f"+ COMPLETE: {plot.get('title', 'the tale')}! The realm breathes free.")
        state.log("+ Victory is yours — and the wilds go on. Wander as you please.")
        state.player.gold += 100
    w.plot = plot
    return True
