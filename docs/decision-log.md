# Decision Log

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
