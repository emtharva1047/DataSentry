# DataSentry Roadmap

## Milestones

- [ ] M1 — Foundation: FastAPI/SQLite APIs and Next.js dashboard are implemented; live browser-to-API verification remains.
- [ ] M2 — Dataset ingestion: validated CSV backend upload, metadata persistence, list/detail APIs, and browser upload/library are implemented; end-to-end browser verification remains.
- [x] M3 — Profiling: schema, missingness, uniqueness, summaries, numeric distributions, and correlations via the read-only profile API.
- [ ] M4 — Quality rules: inferred missingness, exact duplicates, numeric type mismatch, and categorical whitespace/case findings are implemented; explicit schema/domain validation is available through a read-only API. Dashboard schema controls and live browser verification remain.
- [x] M5 — Explainable DQS: completeness, validity, uniqueness, and consistency components expose numerators/denominators; inapplicable dimensions are excluded and active weights are renormalized.
- [ ] M6 — Anomaly detection: read-only IQR, modified robust Z-score, and seeded Isolation Forest APIs plus configurable dashboard controls and evidence views are implemented; controlled ground-truth evaluation remains.
- [ ] M7 — Safe cleaning: advisory recommendations, read-only preview, explicit apply, immutable versions, dashboard operation selection, bounded before/after row evidence, review acknowledgement, version history, and per-version DQS/component comparison are implemented; numeric profile comparison and live browser workflow verification remain.
- [ ] M8 — ML readiness: target checks, imbalance, leakage warnings, and baseline models.
- [ ] M9 — Research lab: seeded corruption, ground truth, metrics, and runtime benchmarks.
- [ ] M10 — Hardening: tests, documentation, research report, demo, and deployment.

## Definition of done

A milestone is complete only when its implementation is present, relevant checks pass, user-facing behavior is documented, and research claims are supported by reproducible evidence.
