# 30-Day Development Roadmap

This plan is scoped for one developer. Protect the research experiment and end-to-end workflow; treat secondary UI polish as optional.

## Week 1 — Foundation and profiling (Days 1–7)
- [ ] Create Next.js frontend and FastAPI backend.
- [ ] Connect frontend → API → SQLite.
- [ ] Implement safe CSV upload and metadata persistence.
- [ ] Build dataset list/detail endpoints.
- [ ] Implement core data profiling.
- [ ] Display dimensions, types, missingness, and summaries.

**Exit criterion:** A CSV can be uploaded, persisted, and profiled through the browser.

## Week 2 — Detection and scoring (Days 8–14)
- [ ] Missing-value, duplicate, schema, and category checks.
- [ ] IQR and robust Z-score detectors.
- [ ] Isolation Forest with reproducible settings.
- [ ] Explainable DQS with component scores and applicability handling.
- [ ] Store issues with evidence and detector metadata.

**Exit criterion:** A user can inspect real detected issues and understand why each was flagged.

## Week 3 — Cleaning and research engine (Days 15–21)
- [ ] Cleaning recommendations and preview.
- [ ] Save cleaned output as a new immutable dataset version.
- [ ] ML-readiness checks and one baseline model path.
- [ ] Synthetic corruption generator with ground truth.
- [ ] Precision, recall, F1, runtime, and downstream metrics.

**Exit criterion:** A reproducible experiment compares at least two detectors on a dataset and defect type.

## Week 4 — Evaluation and presentation (Days 22–30)
- [ ] Finish dashboard and experiment charts.
- [ ] Run experiments across datasets, defect types, rates, and seeds.
- [ ] Add tests, validation, and error handling.
- [ ] Generate research report and document limitations.
- [ ] Prepare demonstration and presentation.

**Exit criterion:** End-to-end demonstration plus reproducible research results.

## Scope cuts if behind schedule
1. Keep CSV only; defer Excel/Parquet.
2. Keep SQLite; defer user roles and cloud deployment.
3. Support one classification and one regression baseline.
4. Keep PDF export optional.
5. Prioritize reproducible benchmarks over cosmetic UI work.
