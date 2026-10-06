"""Strict v1 intermediate representation. No scripts or executable expressions."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Id = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{0,79}$")]
Text = Annotated[str, Field(min_length=1, max_length=4000)]
Number = Annotated[int, Field(ge=0, le=1000000)]
Positive = Annotated[int, Field(ge=1, le=1000000)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)


class AdaptationPolicy(Model):
    mode: Literal["original_inspiration", "public_domain_adaptation", "licensed_adaptation"] = "original_inspiration"
    rights_basis: str = Field(default="", max_length=1000)
    allow_source_names: bool = False

    @model_validator(mode="after")
    def rights(self):
        if self.mode != "original_inspiration" and not self.rights_basis.strip():
            raise ValueError("Higher-fidelity adaptation requires an explicit rights basis")
        if self.mode == "original_inspiration" and self.allow_source_names:
            raise ValueError("Original inspiration cannot reuse source names")
        return self


class Provenance(Model):
    concepts: list[Text] = Field(min_length=1, max_length=20)
    rationale: Text
    source_chunk_ids: list[Id] = Field(default_factory=list, max_length=100)
    transformations: dict[str, str] = Field(default_factory=dict)
    # Abstract design explanations only. Source passages belong to transient input.


class Visual(Model):
    glyph: str = Field(default="?", min_length=1, max_length=1)
    color: str = Field(default="#c8ccda", pattern=r"^#[0-9a-fA-F]{6}$")
    asset_id: Id | None = None
    animation_ids: list[Id] = Field(default_factory=list)


class Entity(Model):
    id: Id
    name: Text
    description: Text
    provenance: Provenance
    visual: Visual = Field(default_factory=Visual)


class BookInterpretation(Model):
    summary: Text
    genre: Text
    tone: list[Text] = Field(min_length=1, max_length=12)
    themes: list[Text] = Field(min_length=1, max_length=20)
    era: Text
    technology: Text
    supernatural_rules: Text
    archetypes: list[Text]
    factions_and_cultures: list[Text]
    social_structures: Text
    geography: Text
    conflicts: list[Text]
    relationships: list[Text]
    narrative_structure: Text
    danger: Text
    morality: Text
    atmosphere: Text
    economy: Text
    combat_style: Text
    important_objects: list[Text]
    progression_opportunities: list[Text]


class CreativeDirection(Model):
    interpretation: BookInterpretation
    world_bible: Text
    gameplay_identity: Text
    originality_strategy: Text
    main_narrative: Text
    side_narratives: list[Text]
    quality_criteria: list[Text] = Field(min_length=3, max_length=20)


class Metadata(Model):
    id: Id
    title: Text
    seed: int = Field(ge=0, le=2**63 - 1)
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_title: Text
    authoring_provider: Text
    adaptation: AdaptationPolicy = Field(default_factory=AdaptationPolicy)
    revision: Positive = 1


class Stat(Entity):
    role: Literal["power", "armor", "speed", "insight", "influence", "luck", "other"]
    minimum: Number = 0
    maximum: Positive = 10000


class Resource(Entity):
    role: Literal["health", "energy", "ammo", "resolve", "other"]
    maximum: Positive
    regen: Number = 0


class DamageType(Entity):
    pass


class Condition(Model):
    kind: Literal["quest_done", "quest_active", "item", "standing", "flag", "level", "visited", "kills", "turn"]
    target: Id | None = None
    amount: Number = 1
    negate: bool = False


class Action(Model):
    kind: Literal["grant_item", "gold", "xp", "standing", "flag", "unlock", "heal", "spawn", "start_quest"]
    target: Id | None = None
    amount: int = Field(default=1, ge=-100000, le=100000)


class Effect(Model):
    kind: Literal["damage", "heal", "shield", "status", "cleanse", "push", "teleport", "summon", "reveal", "negotiate"]
    amount: Number = 0
    damage_type: Id | None = None
    resource_id: Id | None = None
    status_id: Id | None = None
    enemy_id: Id | None = None
    duration: Positive = 1


class Ability(Entity):
    target: Literal["enemy", "self", "all_enemies", "ally"] = "enemy"
    range: int = Field(default=1, ge=0, le=12)
    radius: int = Field(default=0, ge=0, le=6)
    cost: dict[Id, Number] = Field(default_factory=dict)
    cooldown: Number = 0
    accuracy: int = Field(default=100, ge=1, le=100)
    power_scale: int = Field(default=0, ge=0, le=5)
    effects: list[Effect] = Field(min_length=1, max_length=8)


class StatusEffect(Entity):
    tick_damage: Number = 0
    damage_type: Id | None = None
    stat_mods: dict[Id, int] = Field(default_factory=dict)
    skip_turn: bool = False


class EquipmentSlot(Entity):
    pass


class Item(Entity):
    kind: Literal["equipment", "consumable", "material", "artifact"]
    slot_id: Id | None = None
    price: Positive = 1
    stat_mods: dict[Id, int] = Field(default_factory=dict)
    resistances: dict[Id, int] = Field(default_factory=dict)
    ability_ids: list[Id] = Field(default_factory=list)
    effects: list[Effect] = Field(default_factory=list)
    tags: list[Id] = Field(default_factory=list)


class Skill(Entity):
    training_action: Literal["combat", "talk", "explore", "craft", "rest"]
    threshold: Positive = 5
    ability_ids: list[Id] = Field(default_factory=list)
    stat_mods: dict[Id, int] = Field(default_factory=dict)
    prerequisites: list[Id] = Field(default_factory=list)


class Progression(Entity):
    xp_per_level: Positive = 100
    stat_growth: dict[Id, Number] = Field(default_factory=dict)
    resource_growth: dict[Id, Number] = Field(default_factory=dict)
    unlocks: dict[str, list[Id]] = Field(default_factory=dict)
    skill_ids: list[Id] = Field(default_factory=list)


class PlayerDefinition(Entity):
    archetype: Text
    background: Text
    appearance: Text
    motivations: list[Text] = Field(min_length=1)
    personality: list[Text] = Field(min_length=1)
    stats: dict[Id, Number]
    resources: dict[Id, Positive]
    movement: Literal["walk", "sail", "hover"] = "walk"
    equipment_slots: list[Id]
    ability_ids: list[Id] = Field(min_length=1)
    interaction_ability_ids: list[Id] = Field(default_factory=list)
    passive_traits: list[Text] = Field(default_factory=list)
    special_mechanics: list[Id] = Field(default_factory=list)
    starting_items: dict[Id, Positive] = Field(default_factory=dict)
    vulnerabilities: dict[Id, int] = Field(default_factory=dict)
    resistances: dict[Id, int] = Field(default_factory=dict)
    progression_id: Id
    starting_location_id: Id
    species_id: Id | None = None
    class_id: Id | None = None


class ClassDefinition(Entity):
    ability_ids: list[Id] = Field(default_factory=list)
    stat_mods: dict[Id, int] = Field(default_factory=dict)
    progression_id: Id


class Species(Entity):
    culture: Text
    stat_mods: dict[Id, int] = Field(default_factory=dict)


class Faction(Entity):
    ideology: Text
    culture: Text
    goals: list[Text] = Field(min_length=1)
    relationships: dict[Id, int] = Field(default_factory=dict)
    home_location_id: Id


class Region(Entity):
    biome: Text
    atmosphere: Text
    generator: Literal["wilderness", "nautical", "station"] = "wilderness"
    width: int = Field(default=64, ge=32, le=300)
    height: int = Field(default=40, ge=25, le=170)
    danger: int = Field(default=1, ge=1, le=10)
    faction_ids: list[Id] = Field(default_factory=list)
    neighbor_ids: list[Id] = Field(default_factory=list)
    frontier: bool = True


class Location(Entity):
    region_id: Id
    kind: Literal["settlement", "dungeon", "ruin", "shrine", "camp", "farm", "tower"]
    x: int = Field(ge=1, le=298)
    y: int = Field(ge=1, le=168)
    faction_id: Id | None = None
    depth: int = Field(default=1, ge=1, le=5)
    theme: Literal["", "sunken", "overgrown", "scorched"] = ""
    locked_by: list[Condition] = Field(default_factory=list)
    market_items: dict[Id, Positive] = Field(default_factory=dict)
    entry_actions: list[Action] = Field(default_factory=list)
    lore: Text


class DialogueChoice(Model):
    id: Id
    text: Text
    next_node_id: Id | None = None
    conditions: list[Condition] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)


class DialogueNode(Model):
    id: Id
    text: Text
    choices: list[DialogueChoice] = Field(default_factory=list, max_length=8)


class Dialogue(Entity):
    style: Text
    start_node_id: Id
    nodes: list[DialogueNode] = Field(min_length=1, max_length=40)


class NPC(Entity):
    role: Text
    background: Text
    motivation: Text
    personality: Text
    location_id: Id
    faction_id: Id | None = None
    dialogue_id: Id
    relationships: dict[Id, Text] = Field(default_factory=dict)
    services: list[Literal["shop", "heal", "rumor", "history", "scout"]] = Field(default_factory=list)


class EnemyArchetype(Entity):
    family_id: Id
    role: Literal["enemy", "boss", "creature"] = "enemy"
    behavior: Literal["melee", "ranged", "support", "passive"] = "melee"
    stats: dict[Id, Number]
    resources: dict[Id, Positive]
    ability_ids: list[Id] = Field(min_length=1)
    resistances: dict[Id, int] = Field(default_factory=dict)
    vulnerabilities: dict[Id, int] = Field(default_factory=dict)
    loot: dict[Id, Number] = Field(default_factory=dict)
    xp: Positive = 20
    gold: Number = 5
    faction_id: Id | None = None
    negotiation_difficulty: int = Field(default=10, ge=0, le=10000)
    phase_ability_ids: list[Id] = Field(default_factory=list)


class Objective(Model):
    kind: Literal["visit", "kill", "talk", "collect", "craft", "pay", "escort", "choice"]
    target_id: Id
    count: Positive = 1
    destination_id: Id | None = None
    consume: bool = False


class Quest(Entity):
    arc_id: Id
    giver_id: Id
    prerequisites: list[Id] = Field(default_factory=list)
    objectives: list[Objective] = Field(min_length=1, max_length=8)
    reward_actions: list[Action] = Field(min_length=1, max_length=12)
    main: bool = False
    discovered: bool = False
    deadline_turns: Positive | None = None


class EncounterTable(Entity):
    region_id: Id
    location_id: Id | None = None
    enemy_counts: dict[Id, Positive] = Field(min_length=1)
    conditions: list[Condition] = Field(default_factory=list)
    respawn_turns: Number = 0


class Recipe(Entity):
    ingredients: dict[Id, Positive] = Field(min_length=1)
    outputs: dict[Id, Positive] = Field(min_length=1)
    gold_cost: Number = 0
    required_skill_id: Id | None = None


class WorldEvent(Entity):
    conditions: list[Condition] = Field(min_length=1)
    actions: list[Action] = Field(min_length=1)
    once: bool = True
    cooldown_turns: Positive = 20


class HistoryEntry(Model):
    year: int
    event: Text
    entity_ids: list[Id] = Field(default_factory=list)


class Asset(Entity):
    kind: Literal["glyph", "sprite", "portrait", "tile", "icon", "background", "music", "ambient", "combat_sound", "ui_theme", "font", "animation"]
    provider: Literal["existing", "procedural", "local", "remote", "fallback"] = "fallback"
    path: str | None = Field(default=None, max_length=300)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    fallback: Visual = Field(default_factory=Visual)
    prompt: str = Field(default="", max_length=2000)


class Economy(Model):
    currency_name: Text
    starting_gold: Number = 20
    rest_price: Positive = 3
    heal_price: Positive = 5
    caravan_price: Positive = 8
    sell_percent: int = Field(default=50, ge=1, le=90)


class WorldRules(Model):
    health_resource_id: Id
    power_stat_id: Id
    armor_stat_id: Id
    speed_stat_id: Id
    influence_stat_id: Id
    default_damage_type_id: Id
    default_ability_id: Id
    turns_per_day: Positive = 144
    death_gold_percent: int = Field(default=50, ge=0, le=100)
    inventory_capacity: Positive = 80
    supported_mechanics: list[Literal["guard", "quick", "heavy", "ranged", "crafting", "companions", "factions", "frontier", "status", "negotiation"]] = Field(default_factory=list)


class RealmSpec(Model):
    realm_spec_version: Literal[1] = 1
    metadata: Metadata
    creative_direction: CreativeDirection
    visual_style: Text
    audio_direction: Text
    world_rules: WorldRules
    player: PlayerDefinition
    stats: list[Stat] = Field(min_length=1, max_length=32)
    resources: list[Resource] = Field(min_length=1, max_length=12)
    damage_types: list[DamageType] = Field(min_length=1, max_length=16)
    equipment_slots: list[EquipmentSlot] = Field(default_factory=list, max_length=16)
    abilities: list[Ability] = Field(min_length=1, max_length=100)
    status_effects: list[StatusEffect] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    progression: list[Progression] = Field(min_length=1)
    classes: list[ClassDefinition] = Field(default_factory=list)
    species: list[Species] = Field(default_factory=list)
    factions: list[Faction] = Field(min_length=1)
    regions: list[Region] = Field(min_length=1, max_length=12)
    locations: list[Location] = Field(min_length=1, max_length=120)
    npcs: list[NPC] = Field(min_length=1)
    enemies: list[EnemyArchetype] = Field(min_length=1)
    quests: list[Quest] = Field(min_length=1)
    items: list[Item] = Field(default_factory=list)
    crafting: list[Recipe] = Field(default_factory=list)
    encounters: list[EncounterTable] = Field(min_length=1)
    dialogues: list[Dialogue] = Field(min_length=1)
    world_events: list[WorldEvent] = Field(default_factory=list)
    history: list[HistoryEntry] = Field(default_factory=list)
    economy: Economy
    assets: list[Asset] = Field(default_factory=list)

    def entities(self) -> list[Entity]:
        result: list[Entity] = [self.player]
        for name in type(self).model_fields:
            value = getattr(self, name)
            if isinstance(value, list):
                result.extend(x for x in value if isinstance(x, Entity))
        return result

    def index(self) -> dict[str, Entity]:
        return {e.id: e for e in self.entities()}
