# Author, compile, simulate

Before: book readers → proper-noun/event extraction → name mutation → monolithic
world generation → tightly coupled `game.py`/`ui.py` → multi-file mutable save.

Now: whole-book readers → ordered semantic chunk interpretation → hierarchical
synthesis → creative direction/world bible → constrained world-author tools →
originality/quality critique → strict schema/reference/mechanical/topology
validation → immutable fingerprinted RealmPackage → offline simulation → Pygame
presentation → atomic versioned SaveGame.

The archive and original source remain available as the migration baseline.
The runtime wraps original terrain, room/corridor and town builders, and the
presentation wraps the original tile graphics and safe retro sounds. The new
simulation is deliberately independent of book readers and AI modules.

## Boundaries

| Directory | Responsibility |
|---|---|
| `legacy/ascii_rpg/` | Original game; no rules or save behavior rewritten |
| `inkbound/authoring/` | Book ingestion, provider adapters, semantic harness, originality, optional assets |
| `inkbound/realm/` | Strict v1 contract, cross-object validation, package identity/integrity |
| `inkbound/runtime/` | Seeded maps, actors, combat/negotiation, quests, inventory, economy, events, saves and UI |
| `fixtures/` | Original fantasy/horror/science-fiction stories and CI realms |
| `schemas/` | Exported JSON Schema for other future consumers |
| `tests/` | Contract, transport, campaign, determinism, regeneration and presentation checks |

## Contract and execution

`RealmSpec` declares the creative direction, full player definition, stat/resource
roles, equipment slots, abilities/effects/statuses, skills/progression, classes,
species/culture, regions/locations, factions, NPCs/dialogues, enemy/boss/creature
archetypes, quests/objectives, loot, crafting, economy, encounters, history,
events and optional art/audio references. All behavior uses finite enums and
typed conditions/actions. A string from a model is never executed.

The health resource, power/armor/speed/influence stats, default attack and damage
type are references in world rules, not genre constants. A pressure attack,
witness action or induction tool shares one effect implementation. Player
background, representation, starting kit, passives, resources, movement and
progression are authored data. Typed passives modify stats/resistances or restore
resources on turn, visit, kill, negotiation and rest events. Grid movement profiles
allow sailing and hovering across water while walkers remain on land; world
generators create nautical/station/wilderness topology.
More elaborate sailing/zero-gravity physics would need new reusable primitives,
not book-specific scripts.

Global entity IDs must be unique. Validation checks typed references, ability
costs and support, equipment compatibility, health, sustainable damage,
dependencies, goal sources, reachable progression locks, dialogue links and
repeatable reward guards, economy sinks/crafting resale, physical routes and
spawn reachability. Safe automatic repair removes a missing optional visual
reference; creative/mechanical repair uses explicit scoped model revisions and
must pass the full validator. These are bounded abstraction checks rather than
a formal proof for every possible long-running strategy.

Package directories contain `realm.json`, `manifest.json` and optional checksummed
relative asset files. The loader verifies the exact bytes and full spec before
constructing a simulation. Its public spec accessor returns a working copy;
mutating that copy cannot change the published snapshot or its fingerprint.
Older v1 packages retain their original byte identity when new optional fields
are added. No engine code, model SDK or source book is part of
the package. An authoring report can accompany it with tool IDs, attempts and
token/cost accounting.

## Authoring harness

The provider protocol accepts a system instruction, contextual data and tool
schemas, returning typed tool calls and usage. Native Ollama and compatible
HTTP servers are adapters; applications may inject other adapters. Retries apply
to transient transport failure and malformed structured outputs. Optional prose
streaming is separate from atomic compilation. Cache keys include adapter/model,
prompt, tool schemas and protocol version. Cache files contain output, not
requests, raw book input or credentials. Remote calls send the requested book
chunks to the configured service; local servers keep that inference local.

All chunks are read; ordered summaries are reduced six at a time to cover whole
books without a giant prompt. Later construction inherits the interpretation,
creative direction and already authored graph. The tools listed in the original
request are implemented with typed models; `create_dialogue` and explicit chunk
interpretation/critique tools supplement them. Compilation starts with a modest
settlement/region/faction/player/delve/quest/boss slice. The primitive schema can
hold larger hierarchies, while one deliberate slice provides stronger gameplay
evidence than hundreds of unrelated entities.

The default policy asks for transformed expression across multiple dimensions
and retains abstract provenance. Name similarity and ten-word prose overlap
checks catch obvious copying; they cannot certify originality or legal status.
Critique evaluates source connection, coherence, tone, mechanical meaning and
originality. Public-domain/licensed modes require an explicit rights basis.
Source passages are not needed in playable lore/provenance.

Regeneration replaces selected typed objects while preserving their IDs, validates
all remaining references, increments revision and publishes a new package.
Invalid candidates do not mutate the old spec. Save fingerprints intentionally
bind to exact revisions; no unsafe automatic migration of ongoing campaigns is
claimed. Supply the original book to rerun copying/name checks.

## Determinism, saves and performance

Presentation frames never call `tick`, AI, combat or world-generation functions.
Commands advance simulation turns. Random operations derive an independent
stream from the save seed and persisted counter; map/spawn/trade hashes use
SHA-256 rather than process-randomized Python hashes. Maps, floors, enemies,
resources, statuses, ability cooldowns, equipment, quest deeds, events, dialogue,
standing, living escorts, pending overflow loot, frontier origin and return
coordinates persist. Full packs leave reward/encounter finds available for later
pickup; selling, consumable use and crafting protect outstanding main-quest
requirements. Snapshot writes use
temporary files, fsync and atomic replacement. Loading revalidates state and
refuses another package revision.

The minimap base is cached until topology changes. Terrain/layout generation
occurs at package setup and frontier transitions, rather than in rendering.
Optional strip animation only changes presentation time. Fixture measurements
in `artifacts/runtime/render-report.json` cover 30 repeated draws per genre and
verify simulation turns stayed unchanged. Cross-process replay tests vary
`PYTHONHASHSEED` and compare state hashes. Linux tests/render captures do not
prove interactive parity on Windows/macOS or creative enjoyment.

Transport implementation was checked against the official
[Ollama chat reference](https://docs.ollama.com/api/chat) and
[llama.cpp server reference](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).
Local mock tests exercise request shape, argument decoding and usage; actual
model output still requires separate evidence.
