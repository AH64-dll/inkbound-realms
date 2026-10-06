# Architecture audit — before implementation

Audited 2026-10-06, upstream `fdaa7362e0dee0d49b46051997f4da5fba19beae`.
Archive SHA-256: `f19b61d3c3a7986a16c3ab6656ab8f4616b64bdcb321b67a97135dcba7fff752`.
The original archive remains unchanged. Extracted source is in `legacy/ascii_rpg/`.
No rewrite was implemented before this audit. The archive includes two novels in
PDF form, existing saves, and bytecode; these personal/content artifacts are
excluded from new tracked files. The original sample text is used for the audit.

## What this game is

Inkbound Realms is a substantial desktop RPG, rather than an ASCII map demo.
Books seed its names, relationships, elemental climate, callings, rumors, and
history. An expansive wilderness joins walkable towns, seeded multi-floor delves,
an eight-beat main story, and a continuing frontier. Its identity is the tension
between a personal library and a living, strange world: gold quest compass,
annals, rumors heard from people, faction conflicts, small synthesized sounds,
and an ASCII/icons switch. Keep those qualities.

## Complete source map and migration decisions

All paths below are relative to `legacy/ascii_rpg/`. There are 14,023 lines in
the active launcher and source modules. UI backups are historical, not imported.

| System | Authoritative source | Decision and reason |
|---|---|---|
| Entry and CLI | `main.py` (103 lines), `run.sh`, `run.bat` | KEEP original launcher; add package CLI separately |
| Renderer, UI, asset loading | `src/ui.py` (3,091), `ui_legacy/` | WRAP procedural tile drawing; preserve legacy app; evolve package UI |
| Game loop | `App.run`, `App._key` in `src/ui.py` | REFACTOR new simulation boundary: 30 FPS display, input-driven rules |
| Player | `Player`, `random_player`, `apply_class_package`, `apply_race_package` | REPLACE fantasy-specific defaults for package mode with PlayerDefinition |
| Combat and enemies | `src/game.py` (5,241), `Enemy`, `_hit_foe`, `_hurt_player`, `_enemy_turn` | PORT tactical ideas into generic damage/effect/resource/behavior primitives |
| NPCs and dialogue | `worldgen.Character`, `game._talk`, `_descend_town` | PORT roles and town interactions; replace copied flavor with authored dialogue |
| Quests | `src/quests.py` (378), `src/plot.py` (537), `src/board.py` (124) | PORT discover/turn-in/chains; validate stable target IDs and conditions |
| Overworld and frontier | `src/worldgen.py` (1,386), `generate_world`, `grow`, `settle_frontier` | KEEP legacy; WRAP terrain synthesis for package topology; preserve frontier concept |
| Procedural interiors | `src/dungeon.py` (192), `gen_interior`, `gen_town` | WRAP seeded layouts behind runtime map builder |
| Inventory, equipment, crafting | `src/items.py` (492), `game.brew`, shops/housing/consumables | PORT slots, typed gear, goods and recipes; validate configurable slots |
| Character progression | `game.gain_xp`, skills, `src/perks.py` (212) | PORT use-based training and unlocks to data-driven growth/skill trees |
| Save/load and configuration | `src/saves.py` (124), `config.json`, tolerant `from_dict` methods | KEEP legacy saves; new versioned atomic package saves with persisted RNG |
| Book ingestion | `src/ingest.py` (132) | REFACTOR ordered EPUB/text/PDF loading with document/chunk identities |
| Extraction | `src/extract.py` (491), proper noun regex, event/relationship frames | KEEP legacy; REPLACE compiler input with holistic chunk synthesis and review |
| Names | `src/names.py` (99) | KEEP legacy; REPLACE new authoring name mutation with multidimensional synthesis |
| Lore and provenance | `extract.Lore`, `worldgen.provenance_rows`, `src/history.py` (150) | PORT annals; new provenance stores abstract concepts, not source snippets |
| Narrative director | `src/director.py` (995) | PORT paced encounters, remembered choices, consequences and world events |
| Magic | `src/magic.py` (98), `game.cast_spell` | PORT into Ability/Effect primitives; no mandatory fantasy terminology |
| Economy | `src/trade.py` (86), shops/caravans in `game.py` | PORT trade/sinks; replace process-randomized `hash()` prices |
| Audio | `src/sfx.py` (92) | KEEP safe synthesized fallback; WRAP optional package sound references |
| Packaging/updating | `requirements.txt`, `update.bat` | KEEP archival scripts; new root setup must not run machine-specific E: updater |
| Other archive content | `books/sample.txt`, two PDFs, `saves/slot1/*.json`, `run.log`, bytecode | Sample KEEP; personal content stays local, excluded from PR additions |

## Runtime evidence

Installed original dependencies in an isolated virtual environment, launched
the actual Pygame `App.run` loop using the X11 display on the Wayland desktop.
`tools/audit_legacy.py` captures all seven tabs, icons and ASCII modes, town,
dungeon, combat, and post-combat progression. Captures were visually inspected.
Results are in `artifacts/audit/report.json` and `.png` files. Controlled scenario
placement is used for distant towns/delves and one combat encounter; it is not
a claim of a full human campaign playthrough or a fun/creative approval.

Seed 42, sample book: 300×170 map, 51 cities, 89 characters, 48 sites,
3 active and 55 unheard quests. Guard/quick/attack produced counterattacks,
loot and level 2; saved world and player roundtrips matched exactly.
A separate 100-action rules run made 91 moves, fought and looted a beast,
leveled, answered a weather event and observed a warband. Same-seed terrain
and dungeon generation matched; left frontier growth produced width 332
and coordinate shift (32, 0). See `artifacts/audit/playthrough.json`.

## Weaknesses worth fixing

The rules and presentation are separable in practice, but UI imports and invokes
the monolithic game module directly. Core stats, resources, spell IDs, classes,
foe kinds, and equipment slots impose fantasy assumptions. Book influence is
mostly regex/context and frequency. Original book flavor lines and snippets
are reused in cities, NPC dialogue and sagas, so renaming does not provide
transformative originality. New compilation must not inherit that path.
Several commands create unseeded `random.Random()` instances; saves omit their
states. Trading and some barks seed with Python's process-randomized `hash()`.
Therefore repeatable terrain does **not** prove repeatable simulation across
save/load or processes. Existing saves write three files without a transaction.
No committed test suite is present; handoff describes deleted one-off tests.

## Engine decision

Retain Python + Pygame for this migration. The existing 2D game already has a
complete input, audio, resolution, icon and ASCII implementation. Its strongest
systems are Python, so moving immediately to C# would require porting essentially
every rule before verifying book authorship. A package-driven Python runtime can
reuse the original procedural layouts and graphics while separating simulation
from provider dependencies. No Go rewrite is justified.

Godot 4 + C# is a strong future presentation backend for richer animation,
tilemaps and shaders. It requires both the .NET-enabled editor and separate .NET
SDK, and C# Godot 4 web export is currently unsupported. These facts were checked
in the [official documentation](https://docs.godotengine.org/en/stable/tutorials/scripting/c_sharp/c_sharp_basics.html)
on the audit date. Pygame's existing rendering/audio/input support is documented
in its [official reference](https://www.pygame.org/docs/). Neither Godot nor .NET
is installed here. Absence of those tools alone is not the design rationale.

RealmSpec JSON and engine capability checks must be renderer-neutral. A future
Godot consumer can use the same compiled packages; this PR must not claim that
such a consumer exists. Keep the original game runnable and original saves
untouched while new package mode receives its own deterministic rules and tests.
