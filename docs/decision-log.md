# Decision Log

## 2026-09-05 - Preserve Actual Passives on Owned Breeding Results

Verified report: David's local roster contains a male Enchanted Sword at Box 1, slot 20 with only Burly Body and IVs 92/29/38. Replaying the requested Idiosyncratic/Reload Master goal with Stronghold Strategist/Vanguard planned as implants returns `achievable=false`, no complete routes, and one `existing_target` fallback. Its serialized passives correctly contain only Burly Body, with both natural target passives missing.

Cause: the frontend selected the first nonempty group, including incomplete owned candidates, and rendered its first result as a final egg. Root rendering substituted `finalPassives` for the owned Pal's actual passives. This was a display error, not corrupted roster data or an implant calculation error.

Decision: only nodes with breeding parents may receive final-egg rendering. Standalone owned results retain their actual passives and OWNED role. Label the existing-target fallback Best Existing Target and explicitly state that no complete breeding route was found. Preserve planned offspring and implant-ready behavior.

Verification: all 16 frontend tests pass, including new coverage for the reported fallback, complete owned roots, and final offspring with owned parents. JavaScript syntax and diff checks pass. Reproduction used local decoded data read-only; no original saves were modified, and no server was started. Browser visual verification was not performed.

## 2026-09-05 - Simplify Planner Internals and Protect API Writes

Decision: address the four inspected refactoring targets without changing planner ranking or response shapes.

- `breeding_search.py` now checks its donor cache before computing donors. The former `setdefault()` arguments repeated sorting even on cache hits. Cache lifetime remains one final-route search.
- `work.py` uses one metadata builder for species, size, icon, work entries, and source information across suitability, ideal-worker, and owned-worker cards. Each caller retains its own fields and level calculations.
- `bases.py` separates target configuration, candidate construction, scoring, candidate selection, and role-slot allocation into private helpers. `build_base_planner()` is now 61 lines, down from 233; the ranking tuples and slot-allocation order are unchanged.
- `tool.js` uses `postJson()` for the seven JSON POST callers. The shared request function attaches the template's CSRF token to unsafe requests and restricts requests to the same origin. Multipart uploads use the same request and error handling.

Remove all PALS `csrf_exempt` decorators and change the state-changing reload endpoint to POST. Render the token in page metadata, outside the persisted tool form. This completes the previously recorded CSRF follow-up. Existing open pages need refreshing to receive the token.

Upload boundary: use Django's parsed `request.FILES`, since CSRF middleware parses multipart requests before the view runs. The browser sends relative paths in a separate JSON `relativePaths` form field; ordinary multipart clients may omit it and use sanitized filenames. ZIP contents retain their directory structure through the existing ZIP extractor. Delete the now-unused custom MIME parser. Raw binary uploads remain supported with a valid CSRF token. External POST clients now require CSRF credentials as well as authentication; reload clients must use POST.

Verification: captured and compared 2,435 outputs across all local owners, bases, both planner modes, default and constrained settings, all work skills, and species/owned worker cards. Every output matches exactly. All 45 Django tests and 13 JavaScript tests pass, including donor cache reuse, role limits, owned-instance exclusion, missing/invalid CSRF tokens on every POST endpoint, valid JSON requests, and binary/path-preserving uploads. No original saves were modified; live decoding and browser interaction were not exercised.

The cached final-parent search also matches all 180 Shroomer Noct routes from the previous implementation on David's local roster. Python compilation, JavaScript syntax, and diff checks pass.

## 2026-09-05 - Verify Cleanup and Allow Repeat Breeding

Resumed the interrupted cleanup and verified that all intended deletions and both bug fixes persisted. Before further changes, all 33 Django tests and three Bases renderer tests passed. No application imports of the removed optimizer facade or standalone HTTP server remain. The documented CSRF follow-up remains separate work.

Decision: add an opt-in `breedAnyway` request flag and a matching Breeding checkbox. Owned target matches remain available as parents and in ownership metadata, but cannot satisfy a repeat-breeding recommendation on their own. Require parent routes in recommended, progress, and alternative groups. Evaluate final parent pairs directly from owned Pals as well as searched states, because search compaction favors existing matches over repeat offspring. Preserve the existing bounded searches, passive/implant settings, and default behavior when the option is off.

The frontend bypasses the implant-ready presentation in this mode and never falls back to an owned-only result when no route exists. The existing fresh-copy action now checks the option and submits a new search. Form persistence and saved setups include the checkbox through the existing generic form handling.

Verification: 39 Django tests and seven JavaScript tests pass, covering an already-owned target with an actual parent pair, a lone target, same-gender parents, Continue Progress, output gender, default behavior, and the fresh-copy action. JavaScript syntax and diff checks pass. Browser visual verification is unavailable in this session.

Read-only local-roster check: David's Shroomer Noct request with Lavish Hospitality and Service-Minded, implants disabled, and `breedAnyway=true` returned three routes despite existing matches. The top route uses owned male Icelyn and female Gloopie Primo, both with zero setup steps. Python compilation also passes. No save decoding or original-save modification was performed.

## 2026-09-04 - Retire Standalone Compatibility Code

Decision: following the completed Django migration and the request to remove unused original-app code, delete `legacy_http.py` and the `optimizer.py` compatibility facade. Repository searches found only compatibility-test callers; those tests now use the owning services. Old external imports and standalone launch commands are intentionally no longer supported. Keep architecture checks for acyclic imports, a single shared store/cache hook, and imports without server/sync startup.

Remove the unused `WEB` path, three obsolete IV scoring helpers, the unused worker-speed wrapper, the analyzer's unused passive helper/import, and three unreferenced JavaScript functions. Keep `analyze_pal_breeding.py`: save decoding still copies and executes it. Replace the outdated home-page migration placeholder. Previous local comparison artifacts that import the retired facade are historical; the committed tests use the current services.

Fix two confirmed bugs with regression coverage: multipart parsing stripped trailing CR/LF bytes from binary uploads (use the standard-library MIME parser while retaining relative filenames), and perfect-IV Alpha selection preferred a non-Alpha even when an eligible Alpha existed.

Audit scope: inspected PALS service callers, frontend function references, upload handling, IV selection, and planner nesting. An AST scan found no exact four-statement Python blocks occurring more than three times; a four-line JavaScript scan found none either. These scans do not establish absence of semantic duplication. Base planning remains the largest function at 233 lines and reaches four control-flow levels; avoid a speculative planner rewrite in this deletion pass.

Follow-up: session-authenticated mutation endpoints still use `csrf_exempt`; restoring CSRF protection requires coordinated frontend token handling and endpoint tests. This pre-existing behavior is outside the legacy removal and two focused fixes above.

## 2026-09-04 - Render Base Worker Results

The Django frontend's `renderBases()` still returned the JSON debug renderer for every successful plan. Replace that placeholder with worker cards using the existing work-card styles. Show assigned slots and roles, plan capacity, and unfilled minimum roles. Right-now cards display actual planner work levels, owned location, level, gender, stars, and passives; ideal cards display planned levels and breeding links. Keep the backend response and planning algorithms unchanged.

Verification: three Node renderer regression tests pass for successful plans, current-worker details, empty results, gaps, and escaped errors. JavaScript syntax and diff checks pass. Visual browser verification remains outstanding.

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
