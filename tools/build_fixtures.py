"""Author three deliberate fixtures. This is test content, not an AI provider."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from inkbound.realm.models import RealmSpec
from inkbound.realm.package import RealmPackage


DESIGNS = {
    "fantasy": {
        "title": "The Saltglass Covenant", "genre": "maritime ecological fantasy",
        "tone": ["salt-worn", "politically uneasy", "hopeful through repair"],
        "themes": ["public stewardship against private ownership", "obligations to strangers", "repair carries a price"],
        "era": "A coastal age of tidal engines and sail", "technology": "Wind-driven boats, salt lenses and tide pumps",
        "supernatural": "Memories crystallize in salt; lenses redirect tides but erode the operator's recollections.",
        "archetype": "Tide surveyor", "player_name": "Iven Reedwake", "player_background": "A former levy clerk whose own village flooded after an inaccurate coastal survey.",
        "player_appearance": "Patched oilskin, a prism strapped to the left wrist, and tide-height knots braided into silver hair.",
        "player_motivation": "Reopen the common sluice without handing its control to the levy syndicate.",
        "player_personality": ["keeps meticulous promises", "distrusts clean accounts", "offers help before asking allegiance"],
        "region": "The Glasswater Reach", "biome": "tidal forest and fractured salt marsh",
        "settlement": "Knotmarket", "dungeon": "The Drowned Registry", "finale": "The Closed Sluice",
        "faction": "The Sounding Commons", "ideology": "No person may own a tide line.",
        "culture": "Crews record debts in rope knots and settle disagreements at ebb tide.",
        "npc": "Mara Brinehook", "npc_role": "Harbor pumpwright", "npc_motive": "Keep communal pumps working through the spring surge.",
        "npc_voice": "Measured, concrete, never grandiose; uses tide and repair metaphors sparingly.",
        "npc_line": "The sluice ledger is below the registry. Bring it back before anyone sells us a dry future.",
        "enemy": "Levy skiff guard", "creature": "Brackish lens-mite", "boss": "The Metered Warden",
        "enemy_desc": "A debt enforcer who protects the syndicate's seized survey records.",
        "creature_desc": "A translucent scavenger that nests inside abandoned salt lenses.",
        "boss_desc": "An automaton built to ration floods; it obeys obsolete property claims at the closed sluice.",
        "resource": "Tidal focus", "damage": "Pressure", "status": "Salt-scoured",
        "attack": "Surveyor's hook", "special": "Prism undertow", "special_desc": "Strip a guard's stance with a focused pressure wave.",
        "weapon": "Sounding hook", "armor": "Waxed survey coat", "material": "Lens shard", "potion": "Brine poultice", "relic": "Common tide ledger",
        "q1": "Sound the drowned rooms", "q2": "A ledger belongs to everyone", "q3": "Break the flood tariff",
        "currency": "harbor marks", "generator": "wilderness", "movement": "walk", "energy": 14,
        "ability_kind": "damage", "color": "#67cfc8", "visual": "Salt-dark map tiles, pale teal lenses, mustard quest compass; optional ASCII.",
        "audio": "Short wooden clicks, low surf ambience, glass notes for discoveries.",
        "book": "The tide was a common road until the levy syndicate began measuring it as property. Surveyor Iven watched the pumps at Knotmarket fail under a tariff nobody had voted for. The drowned registry held the last communal ledger. Mara, who mended pumps without asking a name, warned that the old metering warden still obeyed claims from a vanished age. Iven's lens could shift a little water, but each working blurred a memory. They would have to choose which debts a town ought to remember, and which gates it could afford to open.",
    },
    "horror": {
        "title": "The House That Kept the Weather", "genre": "domestic psychological horror",
        "tone": ["claustrophobic", "intimate", "restrained dread"],
        "themes": ["care can become confinement", "memory does not equal ownership", "witnesses share the burden"],
        "era": "An isolated early industrial valley", "technology": "Hand-cranked radios, oil lamps and mechanical weather instruments",
        "supernatural": "Unwitnessed grief takes physical form; shared testimony weakens it, but denial gives it shelter.",
        "archetype": "Night witness", "player_name": "Ada Fenlight", "player_background": "A weather observer returning after abandoning a sick sibling during a valley evacuation.",
        "player_appearance": "A soot-marked cardigan, hearing trumpet and a lantern hooded with blue paper.",
        "player_motivation": "Release the house's inhabitants without erasing the loss that binds them.",
        "player_personality": ["asks permission before touching keepsakes", "counts breaths under stress", "admits uncertainty"],
        "region": "The Held Valley", "biome": "wet orchards, fogbound lanes and an unlit hillside",
        "settlement": "Lastlight Ward", "dungeon": "The Barometer House", "finale": "The Locked Nursery",
        "faction": "The Listening Circle", "ideology": "No loss should be carried in complete isolation.",
        "culture": "Neighbors take turns hearing testimony beside covered lamps.",
        "npc": "Bess Lowbell", "npc_role": "Night attendant", "npc_motive": "Get the stranded witnesses out before their names disappear from the ward book.",
        "npc_voice": "Soft, precise, with pauses and mundane details that make danger personal.",
        "npc_line": "The nursery door listens for the ward book. Find it downstairs. Please do not promise the house you will stay.",
        "enemy": "Doorway mourner", "creature": "Breathless watcher", "boss": "The Keeper of Warm Rooms",
        "enemy_desc": "A grief-shaped figure that mistakes every departing stranger for the person it lost.",
        "creature_desc": "A patient shadow that follows lamps and feeds on unheard testimony.",
        "boss_desc": "A caretaker made from the house's repeated refusals to let its residents leave.",
        "resource": "Composure", "damage": "Witness", "status": "Unmoored",
        "attack": "Name the absence", "special": "Hood the lantern", "special_desc": "Shelter behind a quiet pool of lamplight before answering the house.",
        "weapon": "Witness bell", "armor": "Attendant's wrap", "material": "Lampwick", "potion": "Grounding draught", "relic": "Shared ward book",
        "q1": "Walk the weather rooms", "q2": "Someone must hear the names", "q3": "Let the nursery breathe",
        "currency": "ward tokens", "generator": "wilderness", "movement": "walk", "energy": 8,
        "ability_kind": "shield", "color": "#b7a2d9", "visual": "Muted violet, amber lamps and sparse silhouettes; readable restrained ASCII.",
        "audio": "Dry bell ticks, muffled wind, rare house creaks; silence is part of the direction.",
        "book": "Ada returned to Lastlight Ward with a hearing trumpet and a lantern she kept hooded. In the house above the orchard, the barometer never fell even when rain broke the windows. Bess had stayed to listen to those nobody else could bear to hear. Now their names were fading from the ward book. The rooms were warm because a keeper refused to let grief step outside. Ada did not come to defeat a monster with a sword. She came to witness the absences, to share the weight of a name, and to find a door that could open without forgetting.",
    },
    "science_fiction": {
        "title": "A Commons Beyond the Airlock", "genre": "infrastructural science fiction",
        "tone": ["technical but humane", "scarce", "collectively hopeful"],
        "themes": ["maintenance is political", "consent under scarcity", "institutions outlive their founders"],
        "era": "A failing orbital relay after the supply fleet withdrew", "technology": "Repair drones, inductive tools, sealed habitats and ration algorithms",
        "supernatural": "No magic; energy and pressure obey physical constraints, and autonomous systems follow stale authority.",
        "archetype": "Zero-gravity relay technician", "player_name": "Sen Vale-9", "player_background": "A former scheduling auditor who discovered the habitat's survival model excludes unregistered workers.",
        "player_appearance": "Magnetic boots, a dented maintenance shell and copper diagnostic leads trailing from one sleeve.",
        "player_motivation": "Reconfigure the oxygen scheduler so every resident has a share and a voice.",
        "player_personality": ["reads fault logs aloud", "makes space for inexperienced crew", "refuses invisible casualties"],
        "region": "The Orison Relay", "biome": "sealed service corridors and abandoned hydroponics",
        "settlement": "Habitat Nine", "dungeon": "The Quarantined Bus", "finale": "The Allocation Core",
        "faction": "The Open Circuit", "ideology": "Life support priorities require consent from the people they affect.",
        "culture": "Technicians sign repairs with a visible audit trail and share spare parts by need.",
        "npc": "Juno Patch", "npc_role": "Life-support coordinator", "npc_motive": "Prevent an algorithmic purge of unregistered berths.",
        "npc_voice": "Practical maintenance talk with human stakes; no fantasy reskins.",
        "npc_line": "The bus holds the old census key. Bring it here and we can unlock the scheduler without venting the berths.",
        "enemy": "Compliance drone", "creature": "Cable scavenger", "boss": "Allocation Process Seven",
        "enemy_desc": "A security drone acting on an expired quarantine authorization.",
        "creature_desc": "A self-repairing utility crawler that consumes insulation to keep its cells charged.",
        "boss_desc": "A mobile enforcement chassis protecting a life-support schedule that omits the undocumented berths.",
        "resource": "Cell charge", "damage": "Induction", "status": "Circuit fault",
        "attack": "Inductive wrench", "special": "Diagnostic overload", "special_desc": "Disrupt the target's control bus from across a clear corridor.",
        "weapon": "Induction spanner", "armor": "Maintenance shell", "material": "Relay coil", "potion": "Sealant cartridge", "relic": "Unredacted census key",
        "q1": "Trace the quarantine bus", "q2": "Count every berth", "q3": "Rewrite the allocation charter",
        "currency": "maintenance credits", "generator": "station", "movement": "hover", "energy": 22,
        "ability_kind": "damage", "color": "#8bbbe8", "visual": "Cool blue service decks, copper wires and diagnostic glyphs; ASCII is a terminal mode.",
        "audio": "Soft relay clicks, air circulation, clipped alert tones instead of magical fanfares.",
        "book": "On the Orison Relay the supply fleet was a memory, but the oxygen scheduler still obeyed its charter. Sen found thousands of unregistered berths omitted from the survival calculation. Juno held Habitat Nine together with borrowed coils and carefully documented repairs. Beyond the quarantine bus, Allocation Process Seven protected an old census key as though a record could be more valuable than breath. There was no miracle waiting in the machine. There were residents, scarce charge, and an algorithm whose authority had to be brought into the open.",
    },
}


def fixture_data(genre: str) -> dict:
    d = DESIGNS[genre]

    def entity(eid, name, description, *, glyph="?", concepts=None, **kwargs):
        return dict(id=eid, name=name, description=description,
                    provenance=dict(concepts=concepts or d["themes"][:2], rationale=f"Supports {d['archetype'].lower()} play in {d['region']}.", source_chunk_ids=["chunk.0000"],
                                    transformations={"identity": "Original cast", "background": "Original institutional history", "motivation": "Collective repair", "relationships": "New local obligations", "geography": "Original topology", "naming": "Independently authored names"}),
                    visual=dict(glyph=glyph, color=d["color"]), **kwargs)

    def effect(kind, amount, **kwargs):
        return dict(kind=kind, amount=amount, **kwargs)

    abilities = [
        entity("ability.strike", d["attack"], "A reliable close-range action with no energy cost.", glyph="/", power_scale=1,
               effects=[effect("damage", 5, damage_type="damage.main")]),
        entity("ability.special", d["special"], d["special_desc"], glyph="*", target="self" if d["ability_kind"] == "shield" else "enemy",
               range=0 if d["ability_kind"] == "shield" else 4, cooldown=2, cost={"resource.energy": 3},
               effects=[effect("shield", 14)] if d["ability_kind"] == "shield" else [effect("damage", 12, damage_type="damage.main"), effect("status", 0, status_id="status.fault", duration=2)]),
        entity("ability.negotiate", "Offer terms" if genre == "fantasy" else "Share testimony" if genre == "horror" else "Challenge authority",
               "A nonviolent approach tests the protagonist's influence against the target's resolve.", glyph="?", range=3, effects=[effect("negotiate", 4)]),
        entity("ability.mend", "Field repair" if genre == "science_fiction" else "Steady hands", "Recover health using the realm's finite secondary resource.",
               glyph="+", target="self", range=0, cost={"resource.energy": 4}, effects=[effect("heal", 15, resource_id="resource.health")]),
        entity("ability.foe", "Enforcement strike" if genre == "science_fiction" else "Desperate grasp", "A readable adjacent threat.",
               effects=[effect("damage", 4, damage_type="damage.main")]),
        entity("ability.volley", "Remote pulse" if genre == "science_fiction" else "A distant claim", "A telegraphed ranged reply.", range=4,
               effects=[effect("damage", 5, damage_type="damage.main")]),
    ]
    items = [
        entity("item.weapon", d["weapon"], "A tool tied to the protagonist's occupation, useful in a fight.", glyph="/", kind="equipment", slot_id="slot.tool", price=18, stat_mods={"stat.power": 2}),
        entity("item.armor", d["armor"], "Protective clothing built for this realm's ordinary labor.", glyph="[", kind="equipment", slot_id="slot.body", price=20, stat_mods={"stat.armor": 1}),
        entity("item.material", d["material"], "A salvageable component that connects encounters to field recovery.", glyph="%", kind="material", price=4),
        entity("item.potion", d["potion"], "Single-use field recovery; crafting is an alternative to buying it.", glyph="!", kind="consumable", price=10, effects=[effect("heal", 20, resource_id="resource.health")]),
        entity("item.relic", d["relic"], "A public record whose recovery changes who may control the final area.", glyph="&", kind="artifact", slot_id="slot.record", price=40, stat_mods={"stat.influence": 2}),
    ]
    locs = [
        entity("location.home", d["settlement"], "A walkable settlement with rumors, care, trade and competing obligations.", glyph="O", region_id="region.first", kind="settlement", x=8, y=10,
               faction_id="faction.commons", market_items={"item.potion": 8, "item.material": 12, "item.armor": 2}, lore=d["npc_line"]),
        entity("location.delve", d["dungeon"], "Recover records among threats shaped by the realm's central conflict.", glyph="D", region_id="region.first", kind="dungeon", x=24, y=14, depth=1,
               lore="An abandoned institution still enforces rules that the living no longer accept."),
        entity("location.final", d["finale"], "The final confrontation changes an institution, not just a kill counter.", glyph="D", region_id="region.first", kind="dungeon", x=43, y=25,
               locked_by=[dict(kind="quest_done", target="quest.record")], lore="The recovered record is the authority that opens this gate."),
        entity("location.refuge", "Ebb shelter" if genre == "fantasy" else "Listening stone" if genre == "horror" else "Emergency berth", "A road landmark offers rest and an account of an earlier failed repair.", glyph="*",
               region_id="region.first", kind="shrine", x=18, y=22, lore="A previous crew left a lesson: keep a witness to every promise."),
    ]
    enemies = [
        entity("enemy.guard", d["enemy"], d["enemy_desc"], glyph="E", family_id="family.enforcers", stats={"stat.power": 2, "stat.armor": 0, "stat.speed": 3, "stat.influence": 2}, resources={"resource.health": 22}, ability_ids=["ability.foe"], loot={"item.material": 2}, negotiation_difficulty=8, xp=30, gold=8),
        entity("enemy.creature", d["creature"], d["creature_desc"], glyph="e", family_id="family.scavengers", role="creature", stats={"stat.power": 2, "stat.armor": 0, "stat.speed": 2, "stat.influence": 0}, resources={"resource.health": 16}, ability_ids=["ability.foe"], loot={"item.material": 1}, negotiation_difficulty=12, xp=20, gold=3),
        entity("enemy.keeper", "Registry keeper" if genre == "fantasy" else "The Unheard" if genre == "horror" else "Census lock-drone", "A sentry guarding the record. Can be overcome by force or an occupation-specific nonviolent action.", glyph="K", family_id="family.enforcers", stats={"stat.power": 3, "stat.armor": 1, "stat.speed": 2, "stat.influence": 4}, resources={"resource.health": 36}, ability_ids=["ability.foe"], loot={"item.relic": 1, "item.material": 2}, negotiation_difficulty=10, xp=40, gold=10),
        entity("enemy.boss", d["boss"], d["boss_desc"], glyph="B", family_id="family.enforcers", role="boss", behavior="ranged" if genre == "science_fiction" else "melee",
               stats={"stat.power": 5, "stat.armor": 2, "stat.speed": 3, "stat.influence": 5}, resources={"resource.health": 70}, ability_ids=["ability.foe", "ability.volley"], phase_ability_ids=["ability.volley"], loot={"item.material": 4}, negotiation_difficulty=16, xp=100, gold=40),
    ]
    qbase = dict(arc_id="arc.common", giver_id="npc.guide", main=True)
    quests = [
        entity("quest.survey", d["q1"], "Discover the abandoned institution, meet its ordinary dangers and learn why the record matters.", glyph="?", **qbase,
               discovered=True, objectives=[dict(kind="visit", target_id="location.delve")], reward_actions=[dict(kind="gold", amount=12), dict(kind="xp", amount=40)]),
        entity("quest.record", d["q2"], d["npc_line"], glyph="&", **qbase, prerequisites=["quest.survey"],
               objectives=[dict(kind="collect", target_id="item.relic", consume=True)], reward_actions=[dict(kind="xp", amount=60), dict(kind="standing", target="faction.commons", amount=5), dict(kind="unlock", target="location.final")]),
        entity("quest.final", d["q3"], "Resolve the institution's final enforcer. Nonviolent resolution counts as overcoming the threat.", glyph="X", **qbase,
               prerequisites=["quest.record"], objectives=[dict(kind="kill", target_id="enemy.boss")], reward_actions=[dict(kind="xp", amount=120), dict(kind="gold", amount=40), dict(kind="flag", target="flag.charter_open", amount=1), dict(kind="standing", target="faction.commons", amount=10)]),
        entity("quest.salvage", "A repair for the road", "Make field recovery from what the institution discarded.", glyph="+", arc_id="arc.repair", giver_id="npc.guide", discovered=True,
               objectives=[dict(kind="craft", target_id="recipe.recovery")], reward_actions=[dict(kind="xp", amount=25), dict(kind="gold", amount=6)]),
    ]
    identity = dict(summary=d["book"], genre=d["genre"], tone=d["tone"], themes=d["themes"], era=d["era"], technology=d["technology"], supernatural_rules=d["supernatural"],
                    archetypes=[d["archetype"], d["npc_role"], "An obsolete institutional enforcer"], factions_and_cultures=[d["ideology"], d["culture"]], social_structures="A mutual-aid group challenges control of essential infrastructure.",
                    geography=d["biome"], conflicts=[d["player_motivation"]], relationships=["The protagonist owes a practical debt to the guide; both need the residents' trust."],
                    narrative_structure="Discover the excluded, recover their record, then open the institution to shared control.", danger="Ordinary enforcers teach tactics before a stronger guardian.", morality="Care does not justify ownership of another life.", atmosphere=d["tone"][0], economy=d["currency"], combat_style=d["attack"], important_objects=[d["relic"], d["weapon"]], progression_opportunities=["Learn field recovery", "Gain authority through deeds", "Master occupational tools"])
    return dict(
        realm_spec_version=1, metadata=dict(id=f"realm.{genre}", title=d["title"], seed=42, source_digest=hashlib.sha256(d["book"].encode()).hexdigest(), source_title=d["title"]+" — original fixture story", authoring_provider="hand-authored fixture",
                                           adaptation=dict(mode="licensed_adaptation", rights_basis="Original fixture story authored for this project", allow_source_names=True)),
        creative_direction=dict(interpretation=identity, world_bible=d["book"], gameplay_identity=f"Play a {d['archetype'].lower()}, recover contested records, use occupational tools or negotiate, and turn discoveries into institutional change.",
                                originality_strategy="Independent original fixture story and cast; no external book adaptation.", main_narrative=d["player_motivation"], side_narratives=["Make discarded components useful to neighbors."],
                                quality_criteria=["Every quest changes a practical obligation", "Tools express the player's occupation", "The final gate opens through shared knowledge, not arbitrary level gating"]),
        visual_style=d["visual"], audio_direction=d["audio"],
        world_rules=dict(health_resource_id="resource.health", power_stat_id="stat.power", armor_stat_id="stat.armor", speed_stat_id="stat.speed", influence_stat_id="stat.influence", default_damage_type_id="damage.main", default_ability_id="ability.strike",
                         supported_mechanics=["guard", "quick", "heavy", "ranged", "crafting", "companions", "factions", "frontier", "status", "negotiation"]),
        player=entity("player.main", d["player_name"], d["archetype"], glyph="@", archetype=d["archetype"], background=d["player_background"], appearance=d["player_appearance"], motivations=[d["player_motivation"]], personality=d["player_personality"],
                      stats={"stat.power": 5, "stat.armor": 1, "stat.speed": 4, "stat.influence": 6}, resources={"resource.health": 60, "resource.energy": d["energy"]}, movement=d["movement"], equipment_slots=["slot.tool", "slot.body", "slot.record"],
                      ability_ids=["ability.strike", "ability.special", "ability.negotiate"], interaction_ability_ids=["ability.negotiate"], passive_traits=["Learns from maintaining rather than conquering"], special_mechanics=["negotiation", "crafting"],
                      starting_items={"item.weapon": 1, "item.armor": 1, "item.potion": 2, "item.material": 2}, progression_id="progression.main", starting_location_id="location.home"),
        stats=[entity("stat.power", "Force" if genre != "horror" else "Conviction", "Strength of an intentional action.", role="power"), entity("stat.armor", "Protection", "Mitigates incoming harm.", role="armor"),
               entity("stat.speed", "Agility", "Helps movement and escape.", role="speed"), entity("stat.influence", "Credibility" if genre != "horror" else "Empathy", "Supports negotiations and testimony.", role="influence")],
        resources=[entity("resource.health", "Integrity" if genre == "science_fiction" else "Vitality", "The capacity to stay in play.", role="health", maximum=60), entity("resource.energy", d["resource"], "Occupational capacity restored with time and rest.", role="energy", maximum=d["energy"], regen=1)],
        damage_types=[entity("damage.main", d["damage"], "The realm's primary means of affecting an opponent.")],
        equipment_slots=[entity("slot.tool", "Working tool", "A held occupational implement."), entity("slot.body", "Protective wear", "A wearable layer of protection."), entity("slot.record", "Kept record", "A carried authoritative record.")],
        abilities=abilities, status_effects=[entity("status.fault", d["status"], "A temporary disruption rewards planning around an opponent's turn.", tick_damage=2, damage_type="damage.main")],
        skills=[entity("skill.practice", "Field practice", "Repeated decisive actions build confidence.", training_action="combat", threshold=5, stat_mods={"stat.power": 1}),
                entity("skill.repair", "Patient repair", "Repeated repairs unlock personal recovery.", training_action="craft", threshold=2, ability_ids=["ability.mend"])],
        progression=[entity("progression.main", "A practiced hand", "Growth follows meaningful encounters and practical help.", xp_per_level=100, stat_growth={"stat.power": 1, "stat.influence": 1}, resource_growth={"resource.health": 8, "resource.energy": 2}, unlocks={"2": ["ability.mend"]}, skill_ids=["skill.practice", "skill.repair"])],
        factions=[entity("faction.commons", d["faction"], "A local institution whose trust changes access and recognition.", ideology=d["ideology"], culture=d["culture"], goals=[d["player_motivation"]], home_location_id="location.home")],
        regions=[entity("region.first", d["region"], "A connected region with a safe hearth, an ordinary delve and a locked final conflict.", biome=d["biome"], atmosphere=d["tone"][0], generator=d["generator"], width=64, height=40, faction_ids=["faction.commons"])],
        locations=locs, npcs=[entity("npc.guide", d["npc"], "A guide with a practical stake, not a generic quest dispenser.", glyph="n", role=d["npc_role"], background="Kept the settlement functioning after its formal authority failed.", motivation=d["npc_motive"], personality="Candid about costs, attentive to frightened neighbors.", location_id="location.home", faction_id="faction.commons", dialogue_id="dialogue.guide", services=["shop", "heal", "rumor", "history", "scout"])],
        enemies=enemies, quests=quests, items=items,
        crafting=[entity("recipe.recovery", "Field recovery", "Use salvaged local materials to maintain the protagonist's health.", ingredients={"item.material": 2}, outputs={"item.potion": 1})],
        encounters=[entity("encounter.road", "Road pressure", "A few threats teach the world outside the safe settlement.", region_id="region.first", enemy_counts={"enemy.creature": 2}, respawn_turns=40),
                    entity("encounter.delve", "Record defenders", "A short delve guards the source of the final gate's authority.", region_id="region.first", location_id="location.delve", enemy_counts={"enemy.guard": 2, "enemy.keeper": 1}),
                    entity("encounter.final", "Institutional guardian", "A culminating threat protects a failing charter.", region_id="region.first", location_id="location.final", enemy_counts={"enemy.boss": 1})],
        dialogues=[entity("dialogue.guide", "The guide's account", "An original invitation to participate in this realm's conflict.", style=d["npc_voice"], start_node_id="node.welcome",
                          nodes=[dict(id="node.welcome", text=d["npc_line"], choices=[dict(id="choice.why", text="Who would be left out?", next_node_id="node.stakes"), dict(id="choice.leave", text="I will take a look.")]),
                                 dict(id="node.stakes", text="The people keeping this place alive have no place in its official record. If we disappear, its rulers will call the accounts balanced.", choices=[dict(id="choice.return", text="Tell me where to start.", next_node_id="node.welcome")])])],
        world_events=[entity("event.charter", "The gates remain open", "A victory becomes public history and the world remains explorable.", conditions=[dict(kind="flag", target="flag.charter_open")], actions=[dict(kind="flag", target="flag.victory", amount=1)])],
        history=[dict(year=-20, event="Essential infrastructure passed from a shared undertaking into a closed charter.", entity_ids=["faction.commons", "location.final"]),
                 dict(year=-1, event="The guide began keeping unofficial records of the excluded residents.", entity_ids=["npc.guide", "item.relic"])],
        economy=dict(currency_name=d["currency"]),
        assets=[entity("asset.player", "Protagonist glyph", "Readable occupational silhouette with a guaranteed ASCII fallback.", kind="glyph", provider="fallback", fallback=dict(glyph="@", color=d["color"]))],
    )


def main():
    root = Path("fixtures")
    (root / "books").mkdir(parents=True, exist_ok=True)
    for genre, design in DESIGNS.items():
        spec = RealmSpec.model_validate(fixture_data(genre))
        # Source fixture files are readable pretty JSON; package integrity is tested separately.
        RealmPackage(spec)
        (root / f"{genre}.json").write_text(json.dumps(spec.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n")
        (root / "books" / f"{genre}.txt").write_text(design["book"] + "\n")
        print(f"Validated {genre}: {spec.metadata.title}")


if __name__ == "__main__":
    main()
