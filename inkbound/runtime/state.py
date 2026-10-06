"""Save state contains every simulation input, including random stream position."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from inkbound.realm.models import Model
from inkbound.runtime.maps import MapData


class ActorState(Model):
    id: str
    definition_id: str
    map_id: str
    x: int
    y: int
    stats: dict[str, int]
    resources: dict[str, int]
    caps: dict[str, int]
    abilities: list[str]
    statuses: dict[str, int] = Field(default_factory=dict)
    cooldowns: dict[str, int] = Field(default_factory=dict)
    shield: int = 0
    guard: bool = False
    winded: bool = False
    telegraph: bool = False
    enraged: bool = False
    friendly: bool = False
    ally_until: int = 0
    defeated: bool = False


class LootDrop(Model):
    map_id: str
    x: int
    y: int
    items: dict[str, int]


class SaveGame(Model):
    save_game_version: Literal[1] = 1
    package_digest: str
    seed: int
    turn: int = 0
    rng_counter: int = 0
    player: ActorState
    actors: dict[str, ActorState] = Field(default_factory=dict)
    maps: dict[str, MapData]
    return_stack: list[dict[str, str | int]] = Field(default_factory=list)
    inventory: dict[str, int] = Field(default_factory=dict)
    pending_loot: dict[str, LootDrop] = Field(default_factory=dict)
    equipment: dict[str, str] = Field(default_factory=dict)
    gold: int = 0
    xp: int = 0
    level: int = 1
    skills: dict[str, int] = Field(default_factory=dict)
    mastered_skills: list[str] = Field(default_factory=list)
    standing: dict[str, int] = Field(default_factory=dict)
    oath: str | None = None
    quests_known: list[str] = Field(default_factory=list)
    quests_done: list[str] = Field(default_factory=list)
    quests_failed: list[str] = Field(default_factory=list)
    quest_start_turns: dict[str, int] = Field(default_factory=dict)
    kills: dict[str, int] = Field(default_factory=dict)
    visited: list[str] = Field(default_factory=list)
    talked: list[str] = Field(default_factory=list)
    crafted: dict[str, int] = Field(default_factory=dict)
    dialogue_choices: list[str] = Field(default_factory=list)
    flags: dict[str, int] = Field(default_factory=dict)
    unlocked: list[str] = Field(default_factory=list)
    opened_chests: list[str] = Field(default_factory=list)
    event_turns: dict[str, int] = Field(default_factory=dict)
    encounter_turns: dict[str, int] = Field(default_factory=dict)
    encounter_generations: dict[str, int] = Field(default_factory=dict)
    npc_positions: dict[str, list[int]] = Field(default_factory=dict)
    companions: dict[str, str] = Field(default_factory=dict)
    active_dialogue_id: str | None = None
    active_dialogue_node: str | None = None
    active_npc_id: str | None = None
    target_id: str | None = None
    messages: list[str] = Field(default_factory=list)
    annals: list[str] = Field(default_factory=list)
