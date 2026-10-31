# 30-Day Development Roadmap

The project is scoped for one developer. Prioritize a working end-to-end research prototype over optional UI polish. A checkbox is marked complete only after its behavior has been implemented and its relevant checks have been run.

## Week 1 — Foundation and ingestion (Days 1–7)
- [x] FastAPI, SQLite, SQLAlchemy foundation and health/overview APIs.
- [x] CSV upload endpoint with extension, size, row, column, header, and encoding validation.
- [x] Generated storage names, SHA-256 fingerprint, and metadata persistence.
- [x] Dataset list/detail endpoints with safe response schemas.
- [x] Backend API, ingestion, and profiling tests (12 passed with `PYTHONPATH=. pytest -q` in the development environment).
- [x] Next.js App Router dashboard, CSV upload, and dataset library implementation.
- [x] Automated profiling for inferred types, missingness, uniqueness, numeric summaries, categorical frequencies, distributions, and numeric correlations.
- [x] Frontend GitHub Actions lint, TypeScript, and production-build checks (all passed on commit `b414bf5`).
- [ ] Verify a real browser upload and dataset refresh against the running FastAPI service.

**Exit criterion:** A CSV can be uploaded and profiled through the browser. The upload UI and profile API exist; browser-to-API profile interaction remains pending.

## Week 2 — Profiling and quality detection (Days 8–14)
- [x] Read-only column profiling and summary endpoint (`GET /api/datasets/{id}/profile`).
- [ ] Missingness, duplicate, schema/domain, and category inconsistency quality rules with issue evidence.
- [ ] Explainable DQS with explicit denominators and active-weight normalization.
- [ ] Store issue evidence, detector, severity, and affected counts.

The current profile endpoint computes on demand and does not persist profile snapshots. Numeric histograms use 10 bins; Pearson correlation is limited to the first 20 numeric columns to bound response size. Anomaly flags are intentionally not part of the quality score at this stage.

## Week 3 — Anomaly, cleaning, and ML readiness (Days 15–21)
- [ ] IQR, robust Z-score, and Isolation Forest with reproducible parameters.
- [ ] Cleaning preview, explicit apply, and immutable dataset versions.
- [ ] ML-readiness checks and leakage-safe baseline models.

## Week 4 — Research evaluation and delivery (Days 22–30)
- [ ] Seeded synthetic corruption and ground-truth defect labels.
- [ ] Precision, recall, F1, runtime, and downstream ML comparisons.
- [ ] Repeat stochastic runs and report mean/standard deviation.
- [ ] UI integration, automated tests, research report, and demonstration.

## Scope cuts

Keep CSV only, SQLite, one classifier and one regressor. Defer role-based access, cloud-scale processing, Excel/Parquet, and advanced PDF export if needed.
