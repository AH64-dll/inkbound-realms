# Inkbound Realms — book-authored ASCII RPG

Inkbound keeps the original ASCII-RPG's literary worlds, wilderness, rumors,
towns, delves, tactical choices and annals. A new Python authoring layer interprets
a book and compiles a versioned **RealmPackage**. An offline deterministic RPG
runtime plays that data. A new book never rewrites engine code.

The original game is preserved in `legacy/ascii_rpg/`, alongside its original
launcher and save compatibility. Read the [pre-implementation audit](docs/ARCHITECTURE_AUDIT.md)
for the migration decisions and actual original-game evidence.

## Play immediately, with no AI service

Python 3.12 or later:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
inkbound play fixtures/fantasy.json
inkbound play fixtures/horror.json
inkbound play fixtures/science_fiction.json --ascii
```

On Windows, activate with `.venv\Scripts\activate` and use `python` in place of
`python3`. Windows installation and interactive play are not yet verified.

| Realm | Player | Distinctive tools and stakes |
|---|---|---|
| The Saltglass Covenant | Tide surveyor | Pressure waves and disputed communal tide records |
| The House That Kept the Weather | Night witness | Composure, lantern protection and shared testimony |
| A Commons Beyond the Airlock | Relay technician | Cell charge, hover movement and ranged circuit disruption |

These are independently written fixture stories and realms, not outputs claimed
to come from live AI. Their campaigns exercise the same simulation code.

Start on the settlement `O`, press **E** to enter, find the guide `n`, and press
**E** nearby. **J** opens tales and **T** cycles the quest compass. Arrows move;
**A** attacks, **H** uses a heavy action, **Q** a quick action, **D** guards, and
**F** retreats. **C** opens the generated ability list, including nonviolent
actions. **K** crafts, **B** opens settlement trade, **Z** rests. **1–7** select
the familiar tabs; Settings switches icons/ASCII. **F5** saves, **F9** resumes,
**F11** toggles fullscreen. **Esc** closes a conversation or panel. Closing the
window saves automatically. Saves live separately under `saves/`.

To resume on launch:

```bash
inkbound play fixtures/fantasy.json --load
```

To play the original game, with all its existing systems:

```bash
inkbound legacy
```

The archive's personal PDFs and saves remain local and are excluded from the new
tracked source. The original updater targets a machine-specific Windows drive;
the new launcher does not invoke it.

## Author from a book

Start a tool-capable local or remote model server. Configure its URL/model
explicitly; there is no mandatory provider or paid service. Ollama's native chat
protocol and llama.cpp-style compatible chat-completions are implemented.
If a server requires a credential, set `INKBOUND_API_KEY` in your environment.
The key is never stored in a package or cache.

```bash
inkbound compile /path/to/book.epub realms/my-realm \
  --id realm.my-realm --seed 42 \
  --endpoint http://127.0.0.1:11434 --model your-tool-capable-model

# Compatible server, e.g. llama.cpp:
inkbound compile /path/to/book.txt realms/another-realm \
  --id realm.another --dialect compatible \
  --endpoint http://127.0.0.1:8080/v1 --model your-model

# Installed OMP harness, using its existing authenticated provider:
inkbound compile /path/to/book.txt realms/swe-realm \
  --id realm.swe --dialect omp --model devin/swe-2

inkbound play realms/my-realm
```

TXT, text PDFs and spine-ordered EPUBs are supported. Scanned PDFs need OCR;
encrypted PDFs need a decrypted reading copy. All reading chunks, including the
ending, enter hierarchical semantic synthesis. Authoring performs multiple
constrained calls and can take substantial time. `.cache/authoring/` stores
content-addressed outputs; `--max-calls` bounds operations. A model failure or
failed validation leaves no playable incomplete package.

The OMP adapter uses `omp auth-gateway stdio`; it needs the installed OMP CLI and
an authenticated model provider, without a local model server or exported token.
Endpoint arguments apply to the HTTP adapters. OMP authoring uses atomic tool
responses; gameplay never invokes OMP or any model.

`original_inspiration` is the default: new identities, histories, motives,
relationships, geography and expression, rather than mutated names. For material
you can adapt more faithfully, choose `--adaptation public_domain_adaptation` or
`licensed_adaptation` with `--rights-basis 'your explicit basis'`. Optional
`--allow-source-names` is accepted only in those modes. Generated dialogue and
lore must still use fresh prose. Originality heuristics and model critique are
design checks, not proof of legal originality.

## Validate, package, regenerate

```bash
inkbound validate fixtures/fantasy.json
inkbound package fixtures/fantasy.json realms/saltglass
inkbound regenerate realms/saltglass realms/saltglass-v2 \
  --scope faction --ids faction.commons \
  --instruction 'Make their internal disagreement about shared maintenance specific.' \
  --book fixtures/books/fantasy.txt \
  --endpoint http://127.0.0.1:11434 --model your-model
```

Scopes include player, faction, region, enemy family, quest arc, dungeon, items,
visual assets and dialogue style. IDs remain stable; other objects remain
unchanged. The entire candidate is revalidated before a new immutable revision
is published. Keep old packages to resume old saves: a save intentionally refuses
a different package fingerprint. Supplying `--book` enables source-text/name
checks during regeneration; without it, only the persisted creative direction,
mechanical validation and critique are available.

Optional asset providers can use existing files, procedural raster generation,
or registered local/remote callbacks. Every asset has an ASCII/color fallback;
unavailable generators do not prevent play. Packages check every included file's
path and SHA-256. The UI loads optional sprites, strip animations, fonts, themes,
ambient/music and combat audio; otherwise it uses original procedural tiles and
retro synthesized sounds.

## Evidence and remaining gates

```bash
python -m pytest -q
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  inkbound play fixtures/horror.json --frames 3 --capture /tmp/horror.png
```

Tests cover strict schemas, ingestion, recorded tool outputs and HTTP adapters,
references, quest/lock cycles, combat, complete fixture campaigns, progression,
save/resume, cross-process seeds, maps/frontier, regeneration, asset integrity and
UI rendering. [Original audit captures](artifacts/audit/) and
[new runtime captures](artifacts/runtime/) provide review examples. Measured
fixture drawing averages about 4.6–6.3 ms/frame on this Linux workstation with
local CPU inference running concurrently; that is
not a benchmark for arbitrary large generated realms.

Live model authorship, generated-world creative quality, extended human play,
and PR publication remain verification gates. See the
[local authoring experiment](docs/LOCAL_AUTHORING_VERIFICATION.md) for actual
model failures, safeguards and remaining acceptance checks. The package runtime currently
ports the coherent core loop; the original game's full war-age simulation,
perk drafts, housing, alchemy catalog and spell catalog remain available through
the preserved original launcher. This migration does not claim full feature
parity or a Godot backend. See the [implementation ledger](docs/IMPLEMENTATION_PLAN.md)
for the complete original request and pending work.
