# DataSentry Roadmap

## Milestones

- [x] M1 — Foundation: FastAPI/SQLite APIs and Next.js dashboard are implemented; health/overview, production frontend, and backend integration passed the full-stack Chromium workflow on 16 November 2026.
- [x] M2 — Dataset ingestion: validated CSV upload, metadata persistence, list/detail APIs, and browser upload/library passed the full-stack Chromium workflow on 16 November 2026.
- [x] M3 — Profiling: schema, missingness, uniqueness, summaries, numeric distributions, and correlations via the read-only profile API.
- [ ] M4 — Quality rules: inferred missingness, exact duplicates, numeric type mismatch, and categorical whitespace/case findings are implemented; explicit schema/domain validation is available and browser-verified through the read-only API. Interactive dashboard schema-authoring controls are intentionally deferred.
- [x] M5 — Explainable DQS: completeness, validity, uniqueness, and consistency components expose numerators/denominators; inapplicable dimensions are excluded and active weights are renormalized.
- [x] M6 — Anomaly detection: read-only IQR, modified robust Z-score, and seeded Isolation Forest APIs, configurable dashboard controls, evidence views, and the first UCI Wine ground-truth evaluation are implemented and browser-verified. Broader references and anomaly-distribution evaluation remain M9 research expansion.
- [x] M7 — Safe cleaning: advisory recommendations, read-only preview, explicit apply, immutable versions, review acknowledgement, version history, DQS comparison, numeric summary deltas, aligned histograms, and Pearson correlation deltas passed the full-stack Chromium workflow on 16 November 2026.
- [x] M8 — ML readiness and baselines: deterministic diagnostics, profile-driven target/feature selection, and logistic-regression classification plus Ridge regression are implemented with training-only preprocessing. Both task workflows, readiness, holdout metrics, and confusion-matrix rendering passed the full-stack Chromium workflow on 16 November 2026. Repeated-seed and corruption-condition model experiments remain M9 work.
- [ ] M9 — Research lab: deterministic in-memory corruption, exact labels, defect-specific detector integration, and multi-rate/multi-seed benchmark CLIs are implemented. UCI Wine and UCI Bike Sharing detector/classification/regression experiments are documented. The 19 November Isolation Forest contamination-sensitivity sweep completed 9 IF contamination/rate combinations and 27 IF seed runs plus 54 invariant IQR/Robust-Z control runs; measured results and artifact are documented in docs/RESEARCH_RESULTS.md. Additional downstream regression corruption families, categorical-consistency precision improvement, repeated-seed baseline uncertainty, and final research reporting remain.
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
