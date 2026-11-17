# DataSentry Roadmap

## Milestones

- [x] M1 — Foundation: FastAPI/SQLite APIs and Next.js dashboard are implemented; health/overview, production frontend, and backend integration passed the full-stack Chromium workflow on 16 November 2026.
- [x] M2 — Dataset ingestion: validated CSV upload, metadata persistence, list/detail APIs, and browser upload/library passed the full-stack Chromium workflow on 16 November 2026.
- [x] M3 — Profiling: schema, missingness, uniqueness, summaries, numeric distributions, and correlations via the read-only profile API.
- [ ] M4 — Quality rules: inferred missingness, exact duplicates, numeric type mismatch, and categorical whitespace/case findings are implemented; explicit schema/domain validation is available and browser-verified through the read-only API. Interactive dashboard schema-authoring controls are intentionally deferred.
- [x] M5 — Explainable DQS: completeness, validity, uniqueness, and consistency components expose numerators/denominators; inapplicable dimensions are excluded and active weights are renormalized.
- [x] M6 — Anomaly detection: read-only IQR, modified robust Z-score, and seeded Isolation Forest APIs, configurable dashboard controls, evidence views, and the first UCI Wine ground-truth evaluation are implemented and browser-verified. Broader references and threshold sensitivity remain M9 research expansion.
- [x] M7 — Safe cleaning: advisory recommendations, read-only preview, explicit apply, immutable versions, review acknowledgement, version history, DQS comparison, numeric summary deltas, aligned histograms, and Pearson correlation deltas passed the full-stack Chromium workflow on 16 November 2026.
- [x] M8 — ML readiness and baselines: deterministic diagnostics, profile-driven target/feature selection, and logistic-regression classification plus Ridge regression are implemented with training-only preprocessing. Both task workflows, readiness, holdout metrics, and confusion-matrix rendering passed the full-stack Chromium workflow on 16 November 2026. Repeated-seed and corruption-condition model experiments remain M9 work.
- [ ] M9 — Research lab: deterministic in-memory corruption, exact labels, defect-specific detector integration, and a multi-rate/multi-seed benchmark CLI are implemented. UCI Wine detector/classification results are documented. The UCI Bike Sharing mixed-type regression experiment has now run successfully on 17,379 rows at three missingness rates and three seeds, comparing clean, corrupted, and production-cleaned training on one untouched chronological holdout; its artifact and measured results are documented. Broader corruption families, regression detector evaluation, additional references, and final research reporting remain.
- [ ] M10 — Hardening: tests, documentation, research report, demo, and deployment.

## Definition of done

A milestone is complete only when its implementation is present, relevant checks pass, user-facing behavior is documented, and research claims are supported by reproducible evidence.


## Full-stack verification

- [x] Playwright Chromium smoke suite passed on 16 November 2026: one test, one worker, 7.3 seconds, no retry. It covers upload/list/detail, quality/schema/anomaly, cleaning preview/apply, immutable version comparison, ML readiness, classification/regression baselines, and original-file fingerprint preservation.
