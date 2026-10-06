# Evolve ASCII-RPG into a book-authoring compiler and offline realm engine

ASCII-RPG already has a compelling idea and a substantial game: a personal
library seeds a living procedural world. Its current book influence is mostly
keyword/name/event extraction, while fantasy rules and source-derived flavor
are tightly coupled to the runtime. This change preserves and audits the original
game, then introduces a compiled data boundary for richer literary authorship.

The new authoring harness interprets all book chunks, builds creative direction
and a world bible, constructs content through constrained tools, checks
originality and mechanical coherence, and packages a strict versioned RealmSpec.
The deterministic runtime explores, fights or negotiates, crafts, completes
linked objectives, improves a book-derived protagonist, changes faction standing
and records world consequences without inference during play.

| Existing approach | Added approach |
|---|---|
| Keyword-driven generation | Holistic semantic analysis and hierarchical world authorship |
| Hard-coded fantasy assumptions | Configurable stats/resources/slots and generic effects/actions |
| Shallow book influence | Book-level creative direction and occupational player definition |
| Coupled content/runtime | Validated immutable RealmPackage boundary |
| Simple name mutation | Multidimensional creative synthesis, policy/provenance and overlap checks |
| One generated-world pass | Scoped regeneration, stable IDs, critique and full revalidation |

## Preserved features and migration

The upstream archive is unchanged. Extracted original source, launchers and save
compatibility remain available under `legacy/ascii_rpg/`; personal books/saves
are excluded from new tracked additions. Original procedural terrain, interiors,
tile icons and synthesized audio are wrapped by package mode. Its familiar seven
tabs, ASCII option, compass, rumors, delves, annals and continuing world shape the
new presentation. Original war ages, housing, full alchemy/spell catalogs and
perk drafts remain playable through the legacy launcher.

Python/Pygame was retained after running and auditing the existing game. A direct
Godot/C# port would require translating most working rules before proving
authorship. The renderer-neutral JSON contract leaves a later Godot consumer
possible; no Godot backend is claimed here. See `docs/ARCHITECTURE_AUDIT.md` and
`docs/ARCHITECTURE.md` for before/after structure and component decisions.

## Validation and examples

Three original no-inference fixture realms exercise one engine: a tidal surveyor,
a horror witness with lantern protection, and a relay technician with charge and
ranged disruption. Automated campaigns cover discovery, crafting, dungeon
encounters, record recovery, a gated final conflict, faction/world consequences,
progression and save/resume. Tests also cover ingestion, schema/graph failures,
recorded structured tool responses, local HTTP adapter mocks, regeneration,
cross-process determinism, assets and UI rendering.

The current Linux suite passes 231 tests. Overflow finds survive full packs and
save/resume; main-quest items are protected from sale/crafting/consumable use.
Living escorts, typed passives, authored water movement, summon allegiance and
canonical package ordering are exercised. Reading and creative-foundation
guards reject copied source prose before downstream construction.

Review screenshots are under `artifacts/audit/` and `artifacts/runtime/`.
Fixture drawing measured 4.6–6.3 ms/frame on the Linux workstation while local
CPU inference ran concurrently; no
inference runs during rendering. This is scoped evidence, not a broad platform
or large-world performance claim.

## Originality, limitations and pending gates

Default copyrighted-source handling uses original inspiration. Public-domain and
licensed adaptation require a declared rights basis. Dialogue/lore must use fresh
prose; provenance stores abstract inspiration. Similarity heuristics plus critique
catch obvious copying but do not establish legal originality.

This description is a **local PR draft**, kept local at the user's request.
Live provider verification and final review remain required. Recorded fixtures are not advertised
as live AI-generated worlds. Windows/macOS interactive verification, extended
human gameplay/creative review and safe ongoing-save migration across regenerated
revisions remain explicit limits. Broader original-game subsystem ports and richer
genre-specific physics can be added as reusable primitives after this slice meets
its full evidence gates. The complete requested scope remains tracked in
`docs/IMPLEMENTATION_PLAN.md`; this draft does not mark that scope complete.
