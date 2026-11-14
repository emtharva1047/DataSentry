# DataSentry Roadmap

## Milestones

- [ ] M1 — Foundation: FastAPI/SQLite APIs and Next.js dashboard are implemented; live browser-to-API verification remains.
- [ ] M2 — Dataset ingestion: validated CSV backend upload, metadata persistence, list/detail APIs, and browser upload/library are implemented; end-to-end browser verification remains.
- [x] M3 — Profiling: schema, missingness, uniqueness, summaries, numeric distributions, and correlations via the read-only profile API.
- [ ] M4 — Quality rules: inferred missingness, exact duplicates, numeric type mismatch, and categorical whitespace/case findings are implemented; explicit schema/domain validation is available through a read-only API. Dashboard schema controls and live browser verification remain.
- [x] M5 — Explainable DQS: completeness, validity, uniqueness, and consistency components expose numerators/denominators; inapplicable dimensions are excluded and active weights are renormalized.
- [ ] M6 — Anomaly detection: read-only IQR, modified robust Z-score, and seeded Isolation Forest APIs plus configurable dashboard controls and evidence views are implemented; controlled ground-truth evaluation remains.
- [ ] M7 — Safe cleaning: advisory recommendations, read-only preview, explicit apply, immutable versions, dashboard operation selection, bounded before/after row evidence, review acknowledgement, version history, DQS comparison, numeric summary deltas, aligned histograms, and Pearson correlation deltas are implemented; live browser workflow verification remains.
- [ ] M8 — ML readiness: deterministic target, imbalance, leakage, duplicate-split, redundancy, and size diagnostics are implemented at `POST /api/datasets/{id}/ml-readiness`. Seeded logistic-regression classification and Ridge regression baselines are implemented at `POST /api/datasets/{id}/baseline-model` with train-only preprocessing and holdout metrics; dashboard integration, repeated-seed evaluation, and the untouched-test corruption experiment remain.
- [ ] M9 — Research lab: deterministic in-memory corruption, exact labels, defect-specific detector integration, and a multi-rate/multi-seed benchmark CLI are implemented. A reproducible UCI Wine reference workflow and clean-test downstream classification comparison are implemented and executed by GitHub Actions; the first UCI Wine artifact has been inspected and its detector/downstream classification results documented; larger mixed-type references, downstream regression/other corruption conditions, and final research reporting remain.
- [ ] M10 — Hardening: tests, documentation, research report, demo, and deployment.

## Definition of done

A milestone is complete only when its implementation is present, relevant checks pass, user-facing behavior is documented, and research claims are supported by reproducible evidence.
