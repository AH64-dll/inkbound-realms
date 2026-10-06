You are the lead architect and implementation agent for a major redesign of this repository.

Repository:
https://github.com/mokhtar88/ASCII-RPG

The repository currently contains the latest game build inside `ascii_rpg.rar`.

Your job is NOT to blindly rewrite the game from scratch.

Your job is to first reverse-engineer the current version, understand what makes it feel like this game, identify which systems are worth preserving, and then evolve the project into a genuinely AI-driven RPG engine where an arbitrary book can become the creative source material for a playable RPG world.

# 0. Start by auditing the existing game

Before changing any code:

1. Extract `ascii_rpg.rar`.
2. Map the entire project structure.
3. Find the current:
   - entry point
   - rendering system
   - game loop
   - player implementation
   - combat
   - enemies
   - NPCs
   - quests
   - world generation
   - procedural generation
   - inventory/items
   - character progression
   - save system
   - book ingestion
   - text/entity extraction
   - name mutation
   - lore generation
   - UI
   - asset loading
   - audio
   - configuration
4. Run the current game.
5. Play enough of it to understand its intended identity.
6. Write a short architecture audit before beginning the rewrite.

Do not remove working features merely because a cleaner architecture is possible.

Preserve the recognizable feel of the existing project: an unusual procedurally generated RPG whose world is created from literature.

The redesign must feel like an evolution of ASCII-RPG, not an unrelated game using the same repository.

---

# 1. Redefine the core concept

The current concept appears to extract words, entities, names, locations, and other signals from books and procedurally generate content from them.

That idea is good.

The implementation is not ambitious enough.

The new core concept should be:

> A book is interpreted by an AI "world author", compiled into a structured RPG specification, transformed into sufficiently original game content, validated, and then executed by a deterministic RPG engine.

The AI should understand the book holistically rather than simply collecting keywords.

It should understand:

- genre
- tone
- themes
- eras
- technology level
- magic systems
- important archetypes
- factions
- cultures
- creatures
- social structures
- geography
- conflicts
- character relationships
- narrative structure
- danger level
- morality
- atmosphere
- economy
- combat style
- important objects
- progression opportunities

However, the AI must NOT control the game frame-by-frame.

We want:

AI for authorship.

Engine for simulation.

---

# 2. Separate the project into two major systems

Create a clear architectural separation between:

## A. AI Authoring / Compilation Layer

Recommended language: Python.

Responsibilities:

Book ingestion
→ semantic analysis
→ world design
→ RPG design
→ originality transformation
→ structured generation
→ validation
→ optional asset generation
→ final `RealmPackage`

## B. RPG Runtime Engine

Preferred architecture:

Godot 4 + C#

Evaluate this choice against the existing code before committing to it.

If preserving the current engine would produce a better migration path, document why.

Do NOT select Go simply because it is easy to rewrite.

Go + Ebitengine is acceptable if analysis demonstrates that the game benefits from an extremely small custom 2D runtime.

However, strongly consider Godot because this project requires flexible support for:

- sprites
- ASCII rendering
- tile maps
- shaders
- animation
- audio
- UI
- generated assets
- resource loading
- procedural maps
- dynamic content
- save files
- multiple resolutions
- input systems
- future visual upgrades

The engine should remain independent from any particular book or AI provider.

---

# 3. Do NOT let the AI rewrite engine code for each book

This is one of the most important architectural requirements.

A new book should generate DATA, not a new version of the game source code.

Create a strongly defined intermediate representation such as:

`RealmSpec`

Example conceptual structure:

RealmSpec
- metadata
- genre
- tone
- visual_style
- world_rules
- player
- classes
- stats
- skills
- abilities
- damage_types
- status_effects
- factions
- races/species
- NPC archetypes
- enemies
- bosses
- creatures
- locations
- regions
- biomes
- settlements
- dungeons
- quests
- encounters
- items
- equipment
- artifacts
- crafting
- economy
- dialogue styles
- world events
- history
- progression
- main narrative direction
- side narratives
- music/audio direction
- asset references

Use versioned schemas.

For example:

`realm_spec_version: 1`

The engine loads this specification and constructs the game from it.

---

# 4. Build an AI harness with explicit tools

Do not use one enormous prompt that asks the model to invent the entire world.

Build a small agent harness.

The AI should have constrained tool calls such as:

`define_world_identity()`

`define_player_archetype()`

`define_gameplay_rules()`

`create_faction()`

`create_region()`

`create_location()`

`create_character()`

`create_enemy_archetype()`

`create_boss()`

`create_item_family()`

`create_artifact()`

`create_spell_system()`

`create_skill_tree()`

`create_quest_arc()`

`create_encounter_table()`

`create_world_event()`

`define_progression()`

`define_economy()`

`request_asset()`

`validate_relationships()`

`finalize_realm()`

The harness should guide the model through world construction instead of letting it generate arbitrary unvalidated JSON.

The model must be creative, but creativity happens inside well-designed RPG abstractions.

---

# 5. The PLAYER must come from the book

The player cannot always be the same generic RPG character.

Create a flexible `PlayerDefinition`.

For example, if the source material is dark monster-hunting fantasy, the generated protagonist might become an original wandering mutated monster hunter.

If the book is nautical adventure fiction, the protagonist may become a sailor, privateer, explorer, navigator, or captain.

If it is science fiction, the protagonist may use completely different mechanics.

The engine therefore cannot hard-code:

`Player = Warrior`

Instead:

`PlayerDefinition`
controls:

- archetype
- base stats
- resources
- movement
- equipment slots
- combat abilities
- passive traits
- progression
- interaction abilities
- special mechanics
- starting equipment
- vulnerabilities
- resistances
- animations
- visual representation

The same engine must support radically different player definitions.

---

# 6. Build RPG systems as reusable primitives

Do not build one giant fantasy-specific game.

Build reusable primitives that the AI can compose.

For example:

A "magic spell", "witcher sign", "cybernetic ability", "psionic attack", and "religious miracle" may all internally use the same Ability system.

The engine should provide reusable concepts such as:

Entity
Character
Player
NPC
Enemy
Creature
Faction
Region
Location
Item
Equipment
Ability
Effect
Resource
Stat
Quest
Objective
Dialogue
Encounter
LootTable
SpawnTable
Relationship
WorldEvent
Trigger
Condition
Action

Make behavior data-driven wherever practical.

AI-generated worlds should configure these systems rather than create new engine code.

---

# 7. Preserve and dramatically improve the RPG itself

This must still be a GAME.

Do not become so focused on AI generation that the final result becomes a tech demo.

The generated game should support a coherent RPG loop:

explore
→ discover
→ fight/negotiate
→ obtain resources
→ complete objectives
→ improve character
→ influence factions/world
→ unlock new areas
→ face larger conflicts

Preserve good systems already present in the current repository.

Improve weak systems.

The final generated realm should feel deliberately designed rather than procedurally filled with random content.

---

# 8. World generation must become hierarchical

Do not independently generate hundreds of unrelated objects.

Generate from the top down:

Book interpretation

→ Creative Direction

→ World Bible

→ Gameplay Identity

→ Regions

→ Factions

→ Cultures

→ Characters

→ Conflicts

→ Locations

→ Quest Arcs

→ Encounters

→ Items

→ Local details

This lets later content inherit context from earlier decisions.

Every generated object should have reasons for existing in the world.

---

# 9. Solve the copyright/originality problem correctly

Do NOT rely on trivial renaming.

Changing:

Geralt → Geraldo

is not an adequate originality system.

For copyrighted source material, treat the book as inspiration rather than a specification that must be reproduced.

Extract higher-level features such as:

- monster hunter fantasy
- morally ambiguous contracts
- dangerous wilderness
- political conflict
- mutation/alchemy mechanics
- folklore-inspired monsters
- strained relationships between institutions

Then synthesize original expressions of those ideas.

Characters should be transformed across multiple dimensions:

- identity
- background
- appearance
- motivations
- relationships
- abilities
- role
- history
- personality details
- naming
- geography

Likewise transform:

locations,
factions,
quests,
plot events,
artifacts,
creatures,
dialogue,
and lore.

Never copy prose from the source book into generated dialogue or lore.

Never intentionally reconstruct chapters or scenes verbatim.

For public-domain material or user-owned/licensed works, support a configurable higher-fidelity mode.

Introduce something similar to:

`AdaptationPolicy`

with modes such as:

`original_inspiration`
`public_domain_adaptation`
`licensed_adaptation`

Default copyrighted books to `original_inspiration`.

---

# 10. Build a provenance system

The AI should know WHY it generated something.

Internally allow generated content to record abstract inspiration metadata.

Example:

Enemy:
"Grave Stalker"

Inspired concepts:
- nocturnal predator
- cursed battlefield
- scavenger folklore
- necromantic theme

Do NOT store copied source passages unnecessarily.

This system should help debugging and regeneration.

---

# 11. Support partial regeneration

This is extremely important.

If the user likes the generated world but dislikes one faction, they should not need to regenerate everything.

Support regeneration scopes such as:

- player
- faction
- region
- enemy family
- quest arc
- dungeon
- items
- visual assets
- dialogue style

Maintain stable IDs and references.

---

# 12. Asset architecture

Design an asset pipeline where the generated realm can optionally contain:

- ASCII glyphs
- sprites
- portraits
- tiles
- icons
- backgrounds
- music
- ambient sounds
- combat sounds
- UI themes
- fonts
- animations

Do not require generative models for every asset.

Allow asset providers to be interchangeable.

For example:

Existing asset
Procedural asset
Local generator
Remote image model
Remote audio model
Fallback placeholder

The game must remain playable when generative asset APIs are unavailable.

---

# 13. AI provider abstraction

Do not couple the architecture to OpenAI, Anthropic, Gemini, or any single model.

Create a provider-neutral interface.

It should support:

- structured output
- tool calling
- retries
- context management
- caching
- streaming where useful
- local models
- remote models
- token/cost tracking

Most world-generation operations should be reproducible and cacheable.

Never spend AI inference during ordinary frame rendering or basic combat simulation.

---

# 14. Validation layer

Generated content must never be trusted directly.

Build validators.

Validate things such as:

- duplicate IDs
- invalid references
- unreachable quests
- impossible objectives
- missing assets
- broken progression
- invalid equipment
- unkillable required enemies
- zero-damage combat loops
- invalid spawn locations
- circular quest dependencies
- impossible economy
- inaccessible areas
- unsupported abilities
- malformed dialogue trees

Run validation before a `RealmPackage` becomes playable.

Provide automatic repair passes where reasonable.

---

# 15. Determinism

Once generated, a realm should not require the AI to remain playable.

Persist the compiled realm.

Use deterministic seeds for procedural systems.

Given:

RealmPackage + SaveGame + Seed

the runtime should behave predictably.

---

# 16. Migration strategy

Avoid a destructive rewrite where possible.

First identify the strongest systems in the current game.

Then decide whether each component should be:

KEEP
REFACTOR
WRAP
PORT
REPLACE

Document this decision.

Prefer incremental vertical slices.

A good first vertical slice would be:

Book
→ AI interpretation
→ RealmSpec
→ one generated player archetype
→ one region
→ one settlement
→ one faction
→ several enemies
→ one dungeon
→ one quest chain
→ combat
→ progression
→ save/load

Get this genuinely fun before expanding the system horizontally.

---

# 17. Testing

Create automated tests for:

schema parsing,
book ingestion,
AI outputs,
validators,
world references,
save/load,
combat calculations,
quest progression,
procedural generation,
regeneration,
and deterministic seeds.

Also create several fixture realms that require no AI calls so CI can test the complete game.

Include at least:

Fantasy fixture
Horror fixture
Science-fiction fixture

If all three can run on the same runtime without genre-specific hacks, the architecture is moving in the right direction.

---

# 18. Quality bar

Do not accept AI-generated slop.

Reject generated content that is:

generic,
contradictory,
repetitive,
tonally inconsistent,
mechanically meaningless,
or disconnected from the source material.

Create critique/revision passes where necessary.

The AI should first generate coherent creative direction, then generate content, then review its own output against that direction.

Prefer 20 meaningful entities over 200 random ones.

---

# 19. Pull Request requirements

This work is intended to become a serious pull request to improve the original project.

Create a clean PR containing:

- architectural overview
- before/after architecture
- motivation
- preserved existing features
- rewritten systems
- AI authoring architecture
- RealmSpec design
- originality/adaptation design
- new RPG capabilities
- migration notes
- screenshots/examples where possible
- tests
- performance considerations
- limitations
- future work

The PR description should clearly explain why this is an evolution of the original project's idea rather than a replacement of it.

Explicitly highlight improvements such as:

old:
keyword-driven content generation

new:
semantic AI world authorship

old:
hard-coded RPG assumptions

new:
data-driven RPG primitives

old:
shallow book influence

new:
book-level creative direction

old:
runtime tightly coupled to content

new:
RealmPackage abstraction

old:
simple name mutation

new:
transformative creative synthesis

old:
single generated world pass

new:
hierarchical generation + validation + partial regeneration

---

# 20. Final direction

The goal is NOT:

"AI reads a book and makes random fantasy content using its nouns."

The goal is:

"AI reads a piece of literature, understands what makes its world compelling, acts as an RPG creative director, creates an original game world inspired by those qualities, compiles that design into a strict machine-readable RealmPackage, and hands that package to a robust deterministic RPG engine."

Keep the soul of ASCII-RPG.

Make its original concept actually work.

Do not over-engineer systems that do not improve the playable result.

At every major architectural decision ask:

"Does this make it easier for radically different books to become genuinely different, coherent, fun RPGs without rewriting the engine?"

If the answer is no, reconsider the design.

Begin by extracting and auditing the current repository.

Do not implement the rewrite until you understand what is already there.