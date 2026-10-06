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

The initial unconstrained 32K-context server exhausted memory. Subsequent runs
use a temporary user scope with `MemoryMax=4G`, `MemorySwapMax=0`, 16K context,
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

To run against a stable tool-capable compatible server:

```bash
inkbound compile fixtures/books/science_fiction.txt realms/live-relay \
  --id realm.live-relay --dialect compatible \
  --endpoint http://127.0.0.1:18080/v1 --model qwen3-4b \
  --max-calls 120 --timeout 1800
```

A completed experiment must validate the resulting package, inspect its creative
quality, play its linked objectives/combat/progression and verify save/resume.
Structured transport alone is insufficient evidence. The 176 passing automated
tests, fixture campaigns, screenshots and wheel-install smoke test establish
their own narrower scopes.
