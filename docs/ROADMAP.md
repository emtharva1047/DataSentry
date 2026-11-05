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
- [ ] Verify a real browser upload and dataset refresh against the running FastAPI service.

**Exit criterion:** A CSV can be uploaded and profiled through the browser. The upload UI and profile API exist; browser-to-API profile interaction remains pending.

## Week 2 — Profiling and quality detection (Days 8–14)
- [x] Read-only column profiling and summary endpoint (`GET /api/datasets/{id}/profile`).
- [ ] Missingness, duplicate, schema/domain, and category inconsistency quality rules with issue evidence. Missingness, exact duplicates, inferred numeric type mismatch, and categorical whitespace/case findings are implemented. Explicit schema/domain validation is now available at `POST /api/datasets/{id}/quality/validate`; dashboard schema controls and live browser verification remain.
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
- [ ] Cleaning preview, explicit apply, and immutable dataset versions.
- [ ] ML-readiness checks and leakage-safe baseline models.

The anomaly dashboard calls `POST /api/datasets/{id}/anomalies` for the selected dataset. Users can select one or more detectors and set the IQR multiplier, modified-Z threshold, Isolation Forest contamination, random seed, and estimator count. The current dashboard scans all eligible numeric-like columns and displays per-detector counts, bounded row evidence, eligibility reasons, and method notes. API-only column filtering is not exposed in the UI. Results are review flags; the uploaded CSV and DQS remain unchanged. Controlled synthetic-corruption evaluation is still required before M6 can be closed.

## Week 4 — Research evaluation and delivery (Days 22–30)
- [ ] Seeded synthetic corruption and ground-truth defect labels.
- [ ] Precision, recall, F1, runtime, and downstream ML comparisons.
- [ ] Repeat stochastic experiments and report mean/standard deviation.
- [ ] UI integration, automated tests, research report, demo script, known limitations, and reproducibility instructions.

## Scope cuts

Keep CSV only, SQLite, one classifier and one regressor. Defer role-based access, cloud-scale processing, Excel/Parquet, and advanced PDF export if needed.
