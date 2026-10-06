# Book-authored Inkbound Realms implementation ledger

The full supplied specification is `docs/REDESIGN_REQUEST.md`. This ledger tracks
its requirements; unchecked gates remain required, not reclassified as future
work just because a smaller slice runs.

1. [x] Extract, map, launch and audit original before implementation.
2. [x] Evaluate engines and document KEEP/REFACTOR/WRAP/PORT/REPLACE decisions.
3. [x] Strict versioned RealmSpec, PlayerDefinition, adaptation policy,
   provenance, asset manifests, package fingerprints and capability contracts.
4. [x] TXT/PDF/EPUB ingestion, whole-book chunk analysis, creative direction,
   world bible, hierarchical constrained tool harness, critique/revision.
5. [x] Provider-neutral local/remote interfaces: structured tools, retries,
   context, cache, streaming where useful, usage/cost accounting.
6. [x] Multidimensional transformative synthesis and copied-text/name checks;
   explicit public-domain/licensed modes; abstract inspiration provenance.
7. [x] Validators for all listed graph, topology, quest, combat, economy,
   equipment, progression, dialogue, spawn and asset failures; safe repairs.
8. [x] Partial regeneration for player/faction/region/enemy family/quest
   arc/dungeon/items/assets/dialogue style; stable IDs, transactional validation.
9. [x] Deterministic package runtime: exploration, NPCs, combat/negotiation,
   typed effects, resources, gear/loot/crafting/economy, quests, progression,
   faction/world consequences, unlocked areas, bosses, save/load and seeds.
10. [x] Interchangeable assets, ASCII/icons/sprites and audio fallbacks;
    generated realm remains playable without asset APIs.
11. [ ] Live model verification of the coherent first slice from book through settlement/faction/enemies/
    dungeon/quest chain to combat, progression and save/load.
12. [x] Fantasy, horror and science-fiction fixture realms, same runtime,
    no inference in CI; original source/gameplay remains accessible.
13. [x] Automated coverage: schemas, ingestion, AI outputs, validators,
    references, save/load, combat, quests, procedural maps, regeneration,
    deterministic seeds including fresh-process replay.
14. [ ] Runtime launch/capture and visual review, complete playable fixture
    runs, live provider integration when available, performance measurements.
15. [x] README and architecture/migration/originality documentation; PR
    description with before/after, motivation, preserved features, capabilities,
    examples/screenshots, tests, performance, limitations and future work.
16. [ ] Clean commits/branch and published PR (GitHub authentication currently
    invalid; prepare everything locally before requesting an external fix).

Completion requires evidence for each gate and each numbered section of the
original request. Offline fixtures do not prove live semantic authorship;
render smoke tests do not prove a whole campaign is enjoyable. Persist genuine
limitations and verify the largest possible authorized scope before handoff.

Current evidence: 213 tests passed, including HTTP streaming, server-disconnect
and retry checks. The local model returned structured source analysis and a
world identity, but both contained copied passages and cannot be accepted.
Fresh-prose guards now run during reading and creative-foundation construction.
A newer instruction model accepted fresh analysis, creative direction, rules,
region and faction; its settlement validation is being retried.
No validated live-authored realm has been produced yet; repeated global OOM
events from another workload also interrupted the isolated local model server.
Runtime launch/captures, full fixture campaigns and installation via uv succeeded.
Runtime preferences and
living escort save/recovery behavior are covered. Economic reachability uses
conservative bounds; it is not a proof of every strategy or of game balance.
