# 30-Day Development Roadmap

The project is scoped for one developer. Prioritize a working end-to-end research prototype over optional UI polish.

## Week 1 — Foundation and ingestion (Days 1–7)
- [x] FastAPI, SQLite, SQLAlchemy foundation and health/overview APIs.
- [x] CSV upload endpoint with extension, size, row, column, header, and encoding validation.
- [x] Generated storage names, SHA-256 fingerprint, and metadata persistence.
- [x] Dataset list/detail endpoints with safe response schemas.
- [x] Backend ingestion tests (7 passing in the development environment).
- [ ] Browser upload UI and dataset table.
- [ ] Automated profiling: types, missingness, uniqueness, summaries, and distributions.

**Exit criterion:** A CSV can be uploaded and profiled through the browser.

## Week 2 — Profiling and quality detection (Days 8–14)
- [ ] Column profiling and summary endpoints.
- [ ] Missingness, duplicate, schema/domain, and category inconsistency checks.
- [ ] Explainable DQS with explicit denominators and active-weight normalization.
- [ ] Store issue evidence, detector, severity, and affected counts.

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
