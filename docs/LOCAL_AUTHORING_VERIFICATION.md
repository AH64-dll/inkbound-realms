# Local authoring verification

The three checked-in realms are authored fixtures. They are not advertised as
live-model outputs. The required end-to-end live generation gate is still open.

The actual CPU-only experiment uses the official llama.cpp b11438 server and
Qwen3-4B-Q4_K_M GGUF. The downloaded model is 2,497,280,256 bytes; its SHA-256,
checked against the publisher's file metadata, is:

```text
7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5
```

Tools and weights are ignored under `.tools/`; they are not runtime dependencies
or part of the distributed package. The test input is the project's own short
science-fiction story, `fixtures/books/science_fiction.txt`.

The initial unconstrained 32K-context server exhausted memory. Subsequent runs with that model
used a temporary user scope with `MemoryMax=4G`, `MemorySwapMax=0`, 16K context,
quantized Q4 key/value caches, two CPU threads, no warmup/repacking, native Jinja
tool support and reasoning disabled. The inference process is preferentially
eligible for OOM termination; it does not change other services' limits.

One run returned a structured reading analysis and world identity. Both contained
copied source passages; they are unsuitable for publication. Guards now reject
such passages during reading, synthesis and creative-foundation construction,
before building downstream gameplay content. Regression tests cover these
rejections. Whole-candidate checks and critique remain required afterward.

Kernel logs on 2026-10-06 also show repeated global OOM events originating in a
separate memory-heavy workload. These killed the isolated model server even
though its observed memory peak was about 3.1 GiB. No incomplete candidate was
published as a RealmPackage. Completed responses remain cached; caches do not
turn rejected output into accepted content.

The subsequent Qwen3-4B-Instruct-2507 experiment uses a separate verified
GGUF from lmstudio-community, 2,497,280,448 bytes, with SHA-256:

```text
8cdb57cbb880d313736a9bc4e3d3d2485f145b5e19cf33783746e753e82641fc
```

Its temporary scope allows 5 GiB, with 32K context, quantized Q4 caches and four
CPU threads. It produced accepted fresh reading analysis, an original world
foundation, gameplay rules, a region and a faction. Its first settlement attempts
used a display name as a market identifier and were rejected. The harness now
explicitly distinguishes market IDs from display names and retains final error
details. A subsequent structurally valid response classified the home as a camp, so
home-specific validation now requires an actual settlement inside its region.
The server was then restarted with a 16K context, Q8 caches and eight batch
threads after observing slow Q4-cache prompt processing.
A later settlement reused a protected source name. Originality checks now also
run on each content stage, before downstream construction; the model then
produced a fresh settlement called The Resonance Quarter.
Both dungeon stages subsequently passed early checks. The ability stage is
still running. Large construction prompts now omit prior entity provenance
and visual defaults while preserving the complete creative direction, source
coverage, identities, references and mechanics; the compiled data remains full.
On the science-fiction fixture this reduced local-tokenizer context from 11,287
to approximately 4,700 tokens. Final critique still receives the complete realm.
A resumed compile is still pending; these accepted intermediate tools
are not a completed or playable realm. Typed source identities distinguish proper
names from reusable concepts, with actual-source spelling checks.

To run against a stable tool-capable compatible server:

```bash
inkbound compile fixtures/books/science_fiction.txt realms/live-relay \
  --id realm.live-relay --dialect compatible \
  --endpoint http://127.0.0.1:18080/v1 --model qwen3-4b-instruct-2507 \
  --max-calls 120 --timeout 1800
```

A completed experiment must validate the resulting package, inspect its creative
quality, play its linked objectives/combat/progression and verify save/resume.
Structured transport alone is insufficient evidence. The 243 passing automated
tests, fixture campaigns, screenshots and wheel-install smoke test establish
their own narrower scopes.

## Selected OMP backend

The user selected SWE-2 through the OMP harness on this device and requested
keeping the PR local. The temporary Qwen compiler and model server were stopped.
OMP v18.6.1 successfully responded as provider `devin`, model `swe-2`; a subsequent
`omp auth-gateway stdio` probe returned HTTP 200 with a real structured tool call.
No auth broker or exported credential was needed. The adapter forwards atomic
OpenAI-shaped tool requests through OMP's own authentication, retaining bounded
retries and timeouts, schema validation, usage accounting and output-only caches.

A fresh whole pipeline, without reusing Qwen responses, is running with:

```bash
inkbound compile fixtures/books/science_fiction.txt realms/live-swe2 \
  --id realm.live-swe2 --dialect omp --model devin/swe-2 \
  --max-calls 120 --timeout 300
```

Connectivity and accepted intermediate content are still distinct from the
required final package validation, creative inspection and actual campaign.

SWE-2 completed the initial construction and critique. Cross-object validation
found missing items, unreachable dialogue, unavailable enemy ability costs and
incorrect quest target kinds; no invalid package was published. The live run
exposed repair-protocol gaps now covered by regression tests: whole-section
revisions can add missing entities while retaining existing IDs, single-object
ID changes trigger corrective retries, critique targets are constrained to
existing entities in the correct section, and explicit repair plans must pass a
new critique. Validation issues are sorted for reproducible caching. Reviews are
bounded to six rounds within the authoring call budget. Quest repair prompts
spell out target kinds and negotiation's existing enemy-resolution behavior.
The resumed run remains pending final validation and gameplay.
