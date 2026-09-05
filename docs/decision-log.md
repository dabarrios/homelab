# Decision Log

## 2026-09-04 - Complete PALS Optimizer Modularization

Decision: finish the extraction while retaining `optimizer.py` as an explicit compatibility facade. Django views now call the owning services directly, including existing data, save, work, and persistence APIs. Planner behavior and response schemas remain unchanged.

Final ownership:

- `work.py`: shared worker passive scoring, actual and maximum owned work levels, and owned worker cards, alongside species/work suitability helpers.
- `bases.py`: decoded world parsing, base labels and location display, `BASE_WORK_CACHE`, cache invalidation, and both ideal and right-now base planning. It registers its own invalidation hook with `saves.py`; importing the optimizer is no longer required for registration.
- `breeding_state.py`: immutable `State`, owned-row conversion, ranking, gender filtering, and tree transformations, including storage substitution.
- `breeding_search.py`: bounded search and final-parent routes.
- `breeding_progress.py`: existing-progress scoring and explanations.
- `breeding_profiles.py`: automatic work-speed/ranch profile selection and profile-tree restoration.
- `breeding_serialization.py`: tree and result-group serialization.
- `breeding.py`: public `build_plan()` and `profile_passives_payload()` entry points, composing the smaller breeding modules.
- `ivs.py`: IV planning, pair/Pal serialization, owned-target payloads, and implant inventory persistence.
- `legacy_http.py`: the optional standalone HTTP handler, startup sync, and `main()`.

Dependency decision: shared worker scoring must not import base planning. `work.work_card_for_owned_row()` accepts an optional resolved location label. The thin `bases.work_card_for_owned_row()` adapter supplies that label and remains exported through the optimizer for compatibility. Breeding state and serialization can use base location formatting; base planning never imports breeding. IV planning depends on lower-level breeding state, while the public breeding planner uses IV inventory helpers; IV planning does not import the public breeding entry point. All services retain the single `data.STORE` object, and only bases owns the base cache. Tests that replace globals patch the function's owning module.

Legacy assessment: repository searches found no caller of the standalone handler or its startup function outside the optimizer. Django URL routing uses `pals.views`, and the inspected `.vscode/launch.json` starts `django/manage.py runserver 8000`. Retain the legacy adapter because repository evidence cannot establish whether external callers exist. The facade still exports `Handler`, `main`, and `start_startup_live_sync`, including its existing module-execution entry point. Importing either module does not bind a socket or start sync. Django has no dependency on the adapter or facade.

Verification:

- Captured 1,646 representative outputs before extraction: 1,576 owned worker cards; 50 base plans covering five bases, all four owners plus no owner filter, and both planning modes; base parsing; owned-target and IV payloads; and manual, automatic-profile, implant, and invalid-target breeding requests. Expensive breeding searches use a deterministic sample of 12 real roster rows. Full-roster worker/base/IV cases use the existing local decoded data without changing saves.
- Ran PALS tests and compared all baseline outputs after each extraction stage before continuing. The final comparison matches all 1,646 outputs exactly. A cleanup encoding error affecting the apostrophe in `Demon’s Hand` was detected by comparison, repaired, and covered by a regression test. A same-hash-seed comparison against the preserved original source ruled out the initial set-order hypothesis.
- All 31 PALS tests pass (15 existing, 16 added). Added coverage includes worker scoring, cache isolation/invalidation and label refresh, site deduplication, missing data, inheritance, storage substitution, serialization, IV implants/validation, Django delegation, and legacy handler delegation without a socket.
- Architecture tests verify an acyclic import graph, shared store/cache identity, compatibility identity, one cache hook, and fresh imports without server/sync startup. All 72 original function/class definitions remain exported; an AST comparison confirms their bodies are unchanged except for the intentional worker-card adapter.
- `python manage.py check` and `git diff --check` pass. The facade is about 220 lines; the new breeding modules are each under 300 lines. Base and work modules remain cohesive at roughly 500–575 lines each.

Local comparison artifacts and the preserved original source are in ignored `django/local/pals/modularization/`. From `django`, rerun `python local/pals/modularization/compare.py compare`; these local artifacts are not required by the committed tests. Run those with `python manage.py test pals --noinput`.

Remaining scope: no known extraction regressions remain. Legacy external usage remains unverified, so the adapter is retained. Browser behavior, live decoding/sync, and exhaustive full-roster breeding performance were not exercised. Original saves were not modified, and no GUI or HTTP server was started.

## 2026-09-05 - Modularize PALS Optimizer Services

Context: `django/pals/services/optimizer.py` had become the shared data store, save decoder, live-sync handler, base planner, ranch planner, breeding planner, and IV planner in one file. The surrounding service files existed but were mostly placeholders.

Decision: keep `optimizer.py` as the compatibility facade while moving cohesive logic into the existing service modules in small, behavior-preserving slices.

Implementation so far:

- `data.py` owns shared paths, constants, passive metadata helpers, `BreedPal`, `DataStore`, and `STORE`.
- `bases.py` owns base-label persistence.
- `ivs.py` owns implant inventory persistence.
- `saves.py` owns save upload handling, workspace preparation, WSL decoder checks, decode execution, live-save fingerprint/status/refresh, and live-sync module status.

Follow-up decision: `saves.py` exposes `register_refresh_hook()` so decode completion can invalidate dependent caches without importing `optimizer.py`. `optimizer.py` registers its base planner cache clear function after `BASE_WORK_CACHE` is defined.

Current boundary: the larger planner algorithms and legacy HTTP handler still live in `optimizer.py`; Django route handling lives in `views.py`.

## 2026-09-04 - Extract Work Suitability

Decision: `work.py` owns species metadata and icons, work data lookup, verified and projected condensation levels, ownership counts, seed requirements, recommendations, and the work suitability payload. These helpers depend only on `data.py`, so ranch and base planning can reuse them without importing the optimizer.

The Django work suitability endpoint now calls `work.py` directly. `optimizer.py` re-exports the moved names for existing planner and legacy HTTP callers. Both modules use the same `data.STORE` instance; no second data store or reverse import is introduced. Tests and callers that replace module globals must patch the module that owns the function.

Shared work cards and owned-worker scoring remain with the base planner for now. Next, extract those helpers into `work.py` to support moving ranch drops into `ranch.py`, then move base planning, breeding search, and IV planning into their respective modules.

Verification: all 130 work suitability payloads across the current owners, work skills (including no selection), and self-breeder settings matched the pre-extraction output exactly. All 12 PALS tests pass, including a new isolated work suitability test covering ownership, self-breeder filtering, and verified versus projected condensation levels. The test run also exposed earlier extraction gaps: restored the `BreedPal` compatibility export and moved save/data test patches to their owning modules so they exercise their intended fixtures.

## 2026-09-04 - Extract Ranch Drops

Decision: `ranch.py` owns item-text normalization, ranch drop discovery, item grouping, and candidate ranking through `ranch_drops_payload()`. Move the shared `work_card_for_pal()` helper into `work.py`, allowing ranch and base planning to reuse it. Ranch depends only on `data.py` and `work.py`; it does not import the optimizer.

The Django ranch endpoint now calls `ranch.py` directly. `optimizer.py` re-exports the moved functions for its legacy HTTP handler and existing callers. Ranch module status now reports the implemented service as ready.

Preserve the existing selection contract: ownership takes priority in ranking; excluding self-breeders changes the recommended candidate but retains the complete candidate list. If every candidate for an item requires self-breeding, the recommendation falls back to that list.

Verification: all 15 PALS tests pass, including ranch drop matching, owner ranking, self-breeder fallback, and authenticated endpoint filter forwarding. All 10 ranch payloads across current owners and self-breeder settings, plus 598 shared work cards with and without farming selected, matched pre-extraction outputs exactly.

Remaining boundary: owned-worker scoring and base planning still live in `optimizer.py`. Ranch breeding-profile passive selection remains with the breeding search because it depends on that search. Next, extract base planning and its worker helpers; breeding and IV planning follow separately.
