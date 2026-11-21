# 30-Day Development Roadmap

The project is scoped for one developer. Prioritize a working end-to-end research prototype over optional UI polish. A checkbox is marked complete only after its behavior has been implemented and its relevant checks have been run.

## Week 1 — Foundation and ingestion (Days 1–7)
- [x] FastAPI, SQLite, SQLAlchemy foundation and health/overview APIs.
- [x] CSV upload endpoint with extension, size, row, column, header, and encoding validation.
- [x] Generated storage names, SHA-256 fingerprint, and metadata persistence.
- [x] Dataset list/detail endpoints with safe response schemas.
- [x] Backend API, ingestion, and profiling tests.
- [x] Next.js App Router dashboard, CSV upload, and dataset library implementation.
- [x] Automated profiling for inferred types, missingness, uniqueness, numeric summaries, categorical frequencies, distributions, and numeric correlations.
- [x] Frontend GitHub Actions lint, TypeScript, and production-build checks.
- [x] Verify a real browser upload and dataset refresh against the running FastAPI service (Playwright Chromium passed 16 November 2026).

**Exit criterion:** A CSV can be uploaded and profiled through the browser. Verified by the full-stack Chromium journey on 16 November 2026.

## Week 2 — Profiling and quality detection (Days 8–14)
- [x] Read-only column profiling and summary endpoint (`GET /api/datasets/{id}/profile`).
- [ ] Missingness, duplicate, schema/domain, and category inconsistency quality rules with issue evidence. Missingness, exact duplicates, inferred numeric type mismatch, and categorical whitespace/case findings are implemented. Explicit schema/domain validation is available at `POST /api/datasets/{id}/quality/validate` and passed the full-stack browser workflow. Interactive dashboard schema-authoring controls are intentionally deferred as a documented scope cut.
- [x] Dashboard quality report viewer with overall DQS, component denominators, severity counts, issue messages, bounded row evidence, and detector notes.
- [x] Explainable DQS with explicit denominators and active-weight normalization.
- [x] Quality endpoint reports issue evidence, detector code, severity, affected counts, and one-based data-row numbers.

The read-only quality endpoint is `GET /api/datasets/{id}/quality`. The schema-validation endpoint accepts a caller-supplied contract containing expected column names, types (string, integer, number, boolean), required-value flags, optional inclusive numeric bounds, optional allowed-value sets, case sensitivity, and an extra-column policy. It reports missing expected columns, required missing cells, type mismatches, out-of-range values, disallowed values, and unexpected columns with severity and bounded one-based row evidence. Unknown or contradictory request fields are rejected with HTTP 422. The schema checks do not infer business rules, mutate the source CSV, or change the inference-based DQS in this version.

The dashboard quality report viewer displays inferred DQS results. Configurable schema submission is API-only in this increment and remains a frontend integration task. The existing read-only quality endpoint continues to compute on demand and preserves the uploaded source. DQS weights are completeness 30%, validity 30%, uniqueness 20%, and consistency 20%. A component with no assessable denominator is marked inapplicable; remaining weights are renormalized. Validity currently checks inferred numeric-like columns (at least 80% finite numeric parseability and at least two valid values), not user-defined business domains. Categorical whitespace and case variants are review flags; they are not automatically normalized. Severity is high at >=20% affected, medium at >=5% and <20%, and low below 5%.

The profile endpoint also computes on demand and does not persist profile snapshots. Numeric histograms use 10 bins; Pearson correlation is limited to the first 20 numeric columns to bound response size. Anomaly flags are intentionally not part of the quality score.

## Week 3 — Anomaly, cleaning, and ML readiness (Days 15–21)
- [x] IQR, modified robust Z-score, and seeded Isolation Forest API with reproducible parameters.
- [x] Dashboard detector selection, parameter controls, numeric eligibility diagnostics, flagged-row evidence, and source fingerprint display.
- [ ] Controlled ground-truth detector evaluation and comparison metrics.
- [x] Backend advisory recommendations, bounded read-only preview, explicit apply, and immutable dataset versions.
- [x] Dashboard cleaning recommendations, operation selection, read-only preview, explicit review acknowledgement/apply, bounded before/after row evidence, and immutable version history.
- [x] Per-version DQS and component comparison against the original upload, with applicability-aware deltas and source fingerprints.
- [x] Numeric summary, shared-bin histogram, and pairwise Pearson correlation comparison for original and derived versions (up to 20 numeric columns).
- [x] Live browser-to-FastAPI workflow verification (Playwright Chromium, 16 November 2026).
- [x] Read-only ML-readiness diagnostics for target completeness, class imbalance, regression target parseability, suspicious target associations, duplicate feature-vector split risks, feature redundancy, feature missingness, and dataset-size caveats.
- [x] Backend baseline classifier/regressor endpoint with seeded holdout split, train-only type inference/imputation/scaling/encoding, and task-appropriate metrics.
- [ ] Dashboard integration, repeated-seed mean/standard-deviation evaluation, and the clean untouched-test corruption experiment.

The anomaly dashboard calls `POST /api/datasets/{id}/anomalies` for the selected dataset. Users can select one or more detectors and set the IQR multiplier, modified-Z threshold, Isolation Forest contamination, random seed, and estimator count. The current dashboard scans all eligible numeric-like columns and displays per-detector counts, bounded row evidence, eligibility reasons, and method notes. API-only column filtering is not exposed in the UI. Results are review flags; the uploaded CSV and DQS remain unchanged. The first controlled UCI Wine synthetic-corruption evaluation is complete; broader references and threshold-sensitivity analysis are tracked under M9.

The cleaning API exposes GET /api/datasets/{id}/cleaning/recommendations, POST /api/datasets/{id}/cleaning/preview, POST /api/datasets/{id}/cleaning/apply, and GET /api/datasets/{id}/cleaning/versions. Recommendations are advisory only. Preview is read-only and bounded to ten changed rows and ten cell changes per row. Apply requires an explicit request, writes a generated CSV into version storage, and creates an immutable SQLite version record with SHA-256, operation manifest, version number, and optional parent version. Original uploads and prior versions are not overwritten. Numeric median imputation rejects non-numeric or non-finite observed values; categorical mode ties use deterministic pandas mode ordering; lower-case normalization is explicitly high-risk and never recommended by default. A no-op apply returns HTTP 409 without creating a version. The dashboard now supports recommendation selection, choosing an original or derived base version, read-only preview, bounded before/after row/cell evidence, an explicit review acknowledgement before apply, and immutable version history with parent IDs and SHA-256 fingerprints. When a derived version is selected, the quality-comparison endpoint recalculates the original and selected version with the same DQS rules and returns overall/component deltas, applicability changes, issue counts, row/column deltas, and SHA-256 fingerprints. The dashboard displays DQS and component deltas, numeric summary changes, aligned 10-bin histograms, and pairwise Pearson correlation deltas. Numeric comparisons are capped at 20 columns; categorical frequency comparisons are not included. The live browser-to-FastAPI workflow passed in Playwright Chromium on 16 November 2026, including immutable version creation and DQS comparison.

The ML-readiness API is `POST /api/datasets/{id}/ml-readiness`. It requires a target column and task type (`classification` or `regression`); feature columns are optional and default to all columns except the target. It reports target completeness, class distribution/imbalance or regression target numeric parseability, feature missingness, duplicate feature vectors with target excluded, near-exact target copies, near-perfect numeric target associations for regression, exact duplicate feature columns, high-correlation feature pairs, and row/feature-count caveats. Correlation analysis is capped at 20 eligible numeric features and evidence is bounded. The status is `blocked`, `review_required`, or `ready_for_baseline`; it is a heuristic review aid, not a model-quality guarantee. The endpoint is read-only and does not train a model. Dashboard integration is implemented with profile-driven target/feature selection, readiness findings, baseline execution, holdout metrics, and confusion-matrix display; classification and regression dashboard workflows passed browser E2E; repeated-seed baseline evaluation and clean-test corruption comparisons remain M9 research work.

## Week 4 — Research evaluation and delivery (Days 22–30)
- [x] In-memory seeded corruption primitives for missingness, exact duplicate insertion, categorical case/whitespace inconsistency, invalid numeric values, and numerical extremes, with exact cell/row ground-truth labels.
- [x] Binary detector precision/recall/F1/accuracy and TP/FP/TN/FN helper with an explicit zero-division convention.
- [x] Repeated-seed aggregation helper requiring at least three distinct seeds and reporting arithmetic mean plus sample standard deviation (ddof=1).
- [x] Connect applicable rule detectors and the production IQR, robust-Z, and Isolation Forest implementations to defect-specific ground truth; add a reproducible multi-rate/multi-seed benchmark runner and CLI with confusion counts, precision/recall/F1, runtime, and Python-traced memory proxy.
- [x] Add a reproducible UCI Wine public-reference script and GitHub Actions workflow for detector rates 1%, 5%, and 10% across seeds 42, 123, and 2026; publish the full JSON report as a workflow artifact.
- [x] Implement downstream classification comparison across clean, corrupted, and cleaned-corrupted training conditions; split clean data first, corrupt training features only, reuse the untouched clean test set within each seed, and fit preprocessing on each training condition only.
- [x] Inspect the first UCI Wine artifact and record measured three-seed detector and downstream classification results, skipped cases, and limitations in docs/RESEARCH_RESULTS.md.
- [x] Extend detector evaluation to the larger mixed-type UCI Bike Sharing reference; map integer-coded categorical predictors to semantic labels and execute the applicable five-defect benchmark at 1%, 5%, and 10% across seeds 42, 123, and 2026 (21 detector/rate combinations, 63 detector-seed runs, no skipped runs). Measured results are in docs/RESEARCH_RESULTS.md.
- [ ] Extend downstream regression to training-only invalid-value, duplicate, categorical inconsistency, and numerical-anomaly conditions; complete the quality-version-2 categorical re-benchmark on UCI Wine and Bike Sharing (combined whitespace-plus-case precision/recall/F1 = 1.0 at all tested rates); pure case-only public-reference evaluation and additional downstream regression corruption families remain.
- [x] ML dashboard integration.
- [ ] Repeated-seed baseline evaluation, demo script, broader mixed-type/regression experiments, and final delivery report.
- [x] Full browser-to-FastAPI verification (Playwright Chromium, 16 November 2026).

The corruption primitives live in backend/app/services/dataset_research.py; the detector benchmark runner lives in backend/app/services/dataset_benchmark.py and the CLI is backend/scripts/run_detector_benchmark.py. The runner first rejects deterministic pre-existing missing cells, exact duplicate rows, detected categorical whitespace/case variants, and invalid values in inferred numeric-like columns; statistical outliers are retained as baseline observations and count as false positives if flagged. It injects one defect type into a fresh in-memory copy per seed, applies only relevant detectors, and evaluates cell-level labels for missingness/category/type defects and row-level labels for duplicates/numerical anomalies. Numerical anomaly adapters call the same private IQR, robust-Z, and Isolation Forest implementations used by the production API to avoid algorithm drift. It records per-seed confusion counts, precision/recall/F1/accuracy, prediction runtime, and Python tracemalloc peak-allocation delta. The memory proxy excludes some native allocations. Aggregation is withheld if any requested seed is skipped or incomplete. The runner and CLI are implemented and tested. UCI Wine detector/classification results and UCI Bike Sharing detector results plus downstream regression under training-only missingness are documented. Additional regression corruption families, categorical-consistency precision improvement, Isolation Forest contamination sensitivity, repeated-seed baseline uncertainty, demo script, and final delivery report remain outstanding.
## Scope cuts

Keep CSV only, SQLite, one classifier and one regressor. Defer role-based access, cloud-scale processing, Excel/Parquet, and advanced PDF export if needed.


## 15 November 2026 — ML workspace integration

- Added a profile-driven ML workspace to the Next.js dashboard.
- Users select a classification/regression task, target column, and explicit feature set.
- The workspace calls the existing read-only readiness endpoint before enabling baseline training; blockers disable training while warnings remain visible for review.
- The baseline action exposes the configured holdout fraction and random seed and displays task-appropriate metrics, classification confusion counts, split sizes, preprocessing fit scope, software versions, and source fingerprint.
- The UI does not claim that readiness heuristics prove absence of leakage or that one holdout is a general performance estimate.
- Repeated-seed baseline uncertainty, additional downstream regression corruption families, demo script, and final delivery report remain outstanding.


## Full-stack verification increment (16 November 2026)

A Playwright Chromium workflow runs the production Next.js server against a separate FastAPI/SQLite process. Its browser journey uploads a deterministic CSV, verifies metadata and original-file fingerprint handling, exercises quality and anomaly review, explicit schema validation, cleaning preview/apply, immutable version lineage and DQS comparison, ML-readiness diagnostics, and classification/regression baselines. The final PR-head CI execution passed on 16 November 2026: one Chromium test completed in 7.3 seconds without a retry. Backend tests (97), frontend lint/typecheck/build, and the browser workflow all passed. The test asserted original-upload SHA-256 preservation and training-only preprocessing for classification and regression.


## Additional mixed-type downstream regression experiment

- [x] UCI Bike Sharing hourly reference loader and provenance validation (dataset 275, CC BY 4.0, DOI 10.24432/C5W894); 17,379-row source downloaded and validated in GitHub Actions.
- [x] Chronological 75/25 holdout with the final 4,345-row future partition kept untouched; identical test SHA-256 across all nine seed/rate runs.
- [x] Exclude instant/date identifiers and direct target components casual/registered; document the derived day_index and semantic categorical/numeric feature declarations.
- [x] Inject missingness into training features only at 1%, 5%, and 10%; compare clean, corrupted, and production median/mode-cleaned training with Ridge regression.
- [x] Aggregate MAE, RMSE, R², and runtime across seeds 42, 123, and 2026; publish the full JSON artifact and measured results in docs/RESEARCH_RESULTS.md.


The first UCI Bike Sharing workflow completed successfully on 17 November 2026 (GitHub Actions run 44001202119). The experiment ran three rates × three seeds × three training conditions (27 Ridge fits), with no skipped runs. The full artifact and its hashes are recorded in docs/RESEARCH_RESULTS.md. This completes the initial downstream-regression slice, not the full M9 research milestone.


## 18 November 2026 — Mixed-type Bike Sharing detector benchmark

- Added a public-reference adapter for the UCI Bike Sharing hourly dataset.
- Converted all eight integer-coded calendar/weather predictors to explicit semantic labels before synthetic corruption, while retaining the five continuous predictors as numeric. This prevents numeric-looking category codes from being misclassified by the shared numeric-inference heuristic.
- Excluded the target and direct target components from detector input; retained the dataset's existing source/analysis fingerprints and added a detector-frame SHA-256.
- Added a CLI and GitHub Actions workflow for the existing defect-specific benchmark engine. The workflow requests 1%, 5%, and 10% corruption, seeds 42/123/2026, and the production IQR, robust-Z, and Isolation Forest settings.
- The benchmark retains cell-level metrics for missingness, categorical inconsistency, and invalid values, and row-level metrics for duplicates and numerical anomalies. All seed results and skipped reasons remain visible; no aggregate is emitted for incomplete runs.
- The benchmark completed successfully on 18 November 2026 (21 detector/rate combinations, 63 detector-seed runs, no skipped runs). Missingness, duplicate, and invalid-value rules achieved 1.0 precision/recall/F1 in the controlled matching-rule setup; categorical consistency had recall 1.0 but precision 0.010–0.100; IQR and robust Z-score had recall 1.0; fixed-contamination Isolation Forest recall fell to 0.221 and 0.122 at 5% and 10%. Full results and limitations are in docs/RESEARCH_RESULTS.md. Python-traced memory remains a partial allocation proxy.


## 19 November 2026 — Isolation Forest contamination sensitivity (implementation)

- Added a deterministic UCI Bike Sharing sensitivity runner for contamination thresholds 0.01, 0.05, and 0.10, with rates 0.01/0.05/0.10 and seeds 42/123/2026.
- Each setting reuses identical seeded corruption and evaluates the production IQR, robust-Z, and Isolation Forest implementations.
- Per-seed reports now distinguish injected row prevalence from predicted row prevalence; both are calculated over the full reference row count.
- IQR and robust-Z are retained as controls; the runner asserts their confusion counts and quality metrics are invariant across Isolation Forest contamination values.
- The dedicated GitHub Actions workflow completed successfully on 19 November 2026. The artifact was downloaded and inspected; measured results, row-level prevalence, control invariance, hashes, and limitations are recorded in docs/RESEARCH_RESULTS.md.


## 19 November 2026 — Isolation Forest contamination sensitivity (measured)

- The UCI Bike Sharing sensitivity workflow completed 9 Isolation Forest contamination/rate combinations and 27 IF seed runs, plus 54 IQR/Robust-Z control seed runs; no runs were skipped.
- The artifact was downloaded and inspected before results were added to docs/RESEARCH_RESULTS.md.
- Ground-truth row prevalence was 4.8833%, 22.5789%, and 40.8405% for 1%, 5%, and 10% cell corruption across five numeric features.
- At 1% cell corruption, contamination 0.05 gave the best tested F1 (0.9882); at 5% and 10%, contamination 0.10 gave the best tested F1 (0.6138 and 0.3934), but recall remained 0.4428 and 0.2449.
- All six IQR/Robust-Z control groups were invariant across the three Isolation Forest contamination settings.
- Results are specific to this dataset and synthetic anomaly procedure; no universal contamination optimum is claimed. Additional regression corruption families and categorical detector precision remain outstanding.


## 19 November 2026 — Categorical consistency precision revision

The previous categorical rule flagged every value in a casefold-equivalent group, producing many false positives on legitimate category spellings. Quality version 2 now always flags surrounding whitespace, but for case-only variants it flags only non-dominant spellings when there is a unique most-frequent trimmed spelling. Tied groups remain ambiguous and are not case-only findings. The benchmark uses the same production helper. Refreshed Bike Sharing and Wine detector artifacts are required before updating historical performance claims.


## 19 November 2026 — Categorical consistency quality version 2 (measured)

The UCI Wine and Bike Sharing detector workflows were rerun on the quality-version-2 production rule at 1%, 5%, and 10% with seeds 42, 123, and 2026. All 18 categorical rate/seed runs completed without skips and achieved precision/recall/F1 = 1.0. The current synthetic generator injects whitespace and swapped case together, so the public benchmark validates the combined defect but does not isolate pure case-only behavior. The modal/tie heuristic is covered by direct unit tests. See docs/RESEARCH_RESULTS.md for artifact provenance and limitations.


## 20 November 2026 — Pure case-only categorical benchmark (implementation)

- Synthetic corruption now distinguishes combined whitespace-plus-case, whitespace-only, and pure case-only variants; the latter changes letter case only and never adds whitespace.
- Ground-truth schema version 2 records the categorical corruption mode.
- A dedicated UCI Wine and Bike Sharing workflow evaluates the production quality-v2 canonical-spelling rule with three rates and three seeds. Public performance claims remain pending artifact inspection.


## 20 November 2026 — Pure case-only categorical evaluation (measured)

- The dedicated public-reference workflow completed all 18 reference/rate/seed runs (UCI Wine and UCI Bike Sharing × 1%, 5%, 10% × seeds 42, 123, 2026), with no skips.
- Pure case-only injection swaps letter case without adding whitespace. The production quality-v2 detector achieved precision/recall/F1 = 1.0 at every tested rate on both references; F1 sample SD was 0.
- Both clean-reference preflights reported zero missing cells, duplicate rows, categorical inconsistencies, and invalid numeric cells.
- Results are specific to the controlled swapcase generator and the two documented references; they do not estimate real-world performance. Full per-seed metrics, runtimes, memory proxies, hashes, and artifact links are in docs/RESEARCH_RESULTS.md.


## 21 November 2026 — Duplicate-row downstream regression (implementation)

The Bike Sharing regression runner now supports two training-only defect families: missingness in feature cells and exact duplicate insertion of complete feature/target rows. Duplicate corruption operates on the combined training frame so labels remain aligned with their duplicated feature rows. The existing production drop-exact-duplicates transform is applied for the cleaned-corrupted condition. Tests assert that cleaning restores the original training pairs and row count, while the future chronological test partition remains untouched with an identical fingerprint across seeds and rates. The GitHub Actions runner evaluates both conditions at 1%, 5%, and 10% with seeds 42, 123, and 2026. Public measured results are pending artifact inspection.
