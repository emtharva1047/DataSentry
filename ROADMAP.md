# DataSentry Roadmap

## Milestones

- [x] M1 — Foundation: FastAPI/SQLite APIs and Next.js dashboard are implemented; health/overview, production frontend, and backend integration passed the full-stack Chromium workflow on 16 November 2026.
- [x] M2 — Dataset ingestion: validated CSV upload, metadata persistence, list/detail APIs, and browser upload/library passed the full-stack Chromium workflow on 16 November 2026.
- [x] M3 — Profiling: schema, missingness, uniqueness, summaries, numeric distributions, and correlations via the read-only profile API.
- [ ] M4 — Quality rules: inferred missingness, exact duplicates, numeric type mismatch, and categorical whitespace/non-dominant case findings are implemented; quality version 2 treats a uniquely most-frequent spelling as canonical and leaves tied casefold groups ambiguous. Explicit schema/domain validation is available and browser-verified through the read-only API. Interactive dashboard schema-authoring controls are intentionally deferred.
- [x] M5 — Explainable DQS: completeness, validity, uniqueness, and consistency components expose numerators/denominators; inapplicable dimensions are excluded and active weights are renormalized.
- [x] M6 — Anomaly detection: read-only IQR, modified robust Z-score, and seeded Isolation Forest APIs, configurable dashboard controls, evidence views, and the first UCI Wine ground-truth evaluation are implemented and browser-verified. Broader references and anomaly-distribution evaluation remain M9 research expansion.
- [x] M7 — Safe cleaning: advisory recommendations, read-only preview, explicit apply, immutable versions, review acknowledgement, version history, DQS comparison, numeric summary deltas, aligned histograms, and Pearson correlation deltas passed the full-stack Chromium workflow on 16 November 2026.
- [x] M8 — ML readiness and baselines: deterministic diagnostics, profile-driven target/feature selection, and logistic-regression classification plus Ridge regression are implemented with training-only preprocessing. Both task workflows, readiness, holdout metrics, and confusion-matrix rendering passed the full-stack Chromium workflow on 16 November 2026. Repeated-seed and corruption-condition model experiments remain M9 work.
- [ ] M9 — Research lab: deterministic in-memory corruption, exact labels, defect-specific detector integration, and multi-rate/multi-seed benchmark CLIs are implemented. UCI Wine and UCI Bike Sharing detector/classification/regression experiments are documented. The 19 November Isolation Forest contamination-sensitivity sweep completed 9 IF contamination/rate combinations and 27 IF seed runs plus 54 invariant IQR/Robust-Z control runs; measured results and artifact are documented in docs/RESEARCH_RESULTS.md. Quality version 2 was re-benchmarked on UCI Wine and Bike Sharing at 1%, 5%, and 10% across three seeds; combined whitespace-plus-case defects achieved precision/recall/F1 of 1.0 on both references. Pure case-only public-reference evaluation completed on UCI Wine and Bike Sharing at 1%, 5%, and 10% across three seeds; controlled F1 was 1.0 on both references. A training-only exact-duplicate regression condition is now implemented: complete feature/target rows are duplicated together and the production exact-duplicate removal transform is evaluated against the same untouched chronological test partition. The three-seed workflow is configured for missingness and duplicates; measured results are pending artifact inspection. Invalid-value and numerical-anomaly regression conditions, repeated-seed baseline uncertainty, and final research reporting remain.
- [ ] M10 — Hardening: tests, documentation, research report, demo, and deployment.

## Definition of done

A milestone is complete only when its implementation is present, relevant checks pass, user-facing behavior is documented, and research claims are supported by reproducible evidence.


## Full-stack verification

- [x] Playwright Chromium smoke suite passed on 16 November 2026: one test, one worker, 7.3 seconds, no retry. It covers upload/list/detail, quality/schema/anomaly, cleaning preview/apply, immutable version comparison, ML readiness, classification/regression baselines, and original-file fingerprint preservation.


## 19 November 2026 — Isolation Forest contamination sensitivity

- Added a UCI Bike Sharing sensitivity runner for contamination values 0.01, 0.05, and 0.10 across corruption rates 1%, 5%, and 10% and seeds 42, 123, and 2026.
- Reports exact ground-truth and predicted row-level anomaly prevalence per seed; the cell-level corruption rate is not treated as row-level anomaly prevalence.
- Repeats IQR and robust Z-score as controls and checks their confusion counts and quality metrics remain invariant when only Isolation Forest contamination changes.
- The workflow completed successfully on 19 November 2026; the artifact was inspected and measured results, row-prevalence analysis, control invariance, and limitations are recorded in docs/RESEARCH_RESULTS.md. No universal contamination optimum is claimed.


## 19 November 2026 — Isolation Forest contamination sensitivity (measured)

- The UCI Bike Sharing sensitivity workflow completed 9 Isolation Forest contamination/rate combinations and 27 IF seed runs, plus 54 IQR/Robust-Z control seed runs; no runs were skipped.
- The artifact was downloaded and inspected before results were added to docs/RESEARCH_RESULTS.md.
- Ground-truth row prevalence was 4.8833%, 22.5789%, and 40.8405% for 1%, 5%, and 10% cell corruption across five numeric features.
- At 1% cell corruption, contamination 0.05 gave the best tested F1 (0.9882); at 5% and 10%, contamination 0.10 gave the best tested F1 (0.6138 and 0.3934), but recall remained 0.4428 and 0.2449.
- All six IQR/Robust-Z control groups were invariant across the three Isolation Forest contamination settings.
- Results are specific to this dataset and synthetic anomaly procedure; no universal contamination optimum is claimed. Additional regression corruption families and categorical detector precision remain outstanding.


## 19 November 2026 — Categorical consistency precision revision

- Quality version 2 flags surrounding whitespace independently and flags only non-dominant case-only spellings when a casefold-equivalent group has one uniquely most-frequent trimmed spelling.
- Tied casefold groups remain ambiguous and are not penalized for case-only variation; the analysis evidence records canonical counts and ambiguity.
- The benchmark adapter reuses the production helper to prevent detector/quality-rule drift.
- The UCI Bike Sharing detector benchmark is rerun under the revised rule before any updated precision claim is recorded.


## 19 November 2026 — Categorical consistency quality version 2 (measured)

- Refreshed UCI Wine and UCI Bike Sharing detector benchmarks on the same 1%/5%/10% rates and seeds 42/123/2026.
- All 18 categorical rate/seed combinations completed with no skips; the combined whitespace-plus-case defect achieved precision/recall/F1 = 1.0 on both references.
- The synthetic generator injects whitespace and swapped case together, so these public benchmarks do not independently establish pure case-only performance. Direct tests cover unique modal spellings and tied ambiguous groups.
- Full measured results, artifact hashes, and limitations are recorded in docs/RESEARCH_RESULTS.md.


## 20 November 2026 — Pure case-only categorical evaluation (implementation)

- Added three explicit synthetic categorical modes: historical combined whitespace-plus-case, whitespace-only, and pure case-only.
- Pure case-only mode swaps alphabetic case without adding whitespace and excludes values unchanged by `swapcase()` from eligible candidates.
- Ground-truth payload schema is version 2 and records the selected categorical mode.
- Added a shared benchmark parameter so the production quality-v2 detector is evaluated against exact case-only cell labels.
- Added a dedicated public-reference runner and GitHub Actions workflow for UCI Wine and semantically mapped UCI Bike Sharing, at 1%, 5%, and 10% across seeds 42, 123, and 2026.
- Public results remain pending until the workflow completes and its JSON artifact is inspected.


## 20 November 2026 — Pure case-only categorical evaluation (measured)

- Completed 18 reference/rate/seed runs: two public references × three corruption rates × three seeds; no skipped runs.
- The mode swaps alphabetic case only and adds no whitespace. Ground-truth schema v2 records the subtype.
- The production quality-v2 categorical rule achieved precision/recall/F1 = 1.0 for all tested rates on UCI Wine (178 rows; derived alcohol_band) and UCI Bike Sharing (17,379 rows; eight semantic categorical predictors). F1 sample standard deviation was 0 across the three seeds for every rate.
- Clean-reference preflight reported zero missing cells, exact duplicate rows, pre-existing categorical findings, and invalid numeric cells on both references.
- Runtime, Python-traced allocation proxies, artifact hashes, and limitations are recorded in docs/RESEARCH_RESULTS.md. The result is controlled synthetic evidence, not a real-world performance estimate.


## 21 November 2026 — Duplicate-row downstream regression (implementation)

- Generalized the Bike Sharing downstream Ridge experiment to support training-only exact duplicate insertion in addition to missingness.
- Duplicate source rows are injected into a combined training frame containing all selected predictors and the regression target, preserving feature/target alignment.
- The production drop-exact-duplicates cleaning transform is applied to the corrupted training frame; tests assert that it restores the original training feature/target pairs and row count.
- The chronological future test partition is never passed to corruption or cleaning; its SHA-256 fingerprint is retained and must remain identical across seeds.
- The CLI and GitHub Actions workflow now run missingness and duplicate conditions at 1%, 5%, and 10% over seeds 42, 123, and 2026.
- Research results remain pending until the workflow completes and its JSON artifact is inspected.
