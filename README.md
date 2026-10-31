# DataSentry

**An intelligent framework for automated dataset quality assessment, anomaly detection, and machine-learning readiness analysis.**

DataSentry is a research-oriented full-stack application that profiles tabular datasets, detects quality issues using statistical, rule-based, and machine-learning techniques, recommends transparent cleaning actions, and evaluates how data defects affect downstream ML models.

> **Project status:** Early development / research prototype. Benchmark results will only be reported after reproducible experiments have been run.

## Research focus

The project investigates a hybrid approach to data-quality assessment.

Research questions:
1. How accurately do rule-based, statistical, and ML detectors identify injected data-quality defects?
2. How does a hybrid detector compare with individual detection methods?
3. Does recommended cleaning improve downstream model performance under controlled corruption?
4. How do dataset size and corruption rate affect processing time and detection quality?

## Planned capabilities

- CSV upload, validation, metadata, and dataset versioning.
- Automated profiling: dimensions, inferred types, missingness, cardinality, descriptive statistics, and distributions.
- Rule-based checks: missing values, exact duplicates, schema violations, and categorical inconsistencies.
- Statistical anomaly detection: IQR and robust Z-score.
- ML anomaly detection: Isolation Forest, with configurable parameters and review-first results.
- Explainable Data Quality Score (DQS) with published component scores and weights.
- Cleaning recommendations with preview and immutable source-file preservation.
- ML-readiness checks for target completeness, class imbalance, suspicious leakage indicators, and duplicate train/test records.
- Synthetic corruption lab with ground-truth labels and benchmark reporting using precision, recall, F1, runtime, and downstream model metrics.

## Technology stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, React, TypeScript, Tailwind CSS |
| Backend | Python 3.12, FastAPI |
| Database | SQLite initially, SQLAlchemy ORM |
| Data processing | Pandas, NumPy, SciPy |
| Machine learning | Scikit-learn |
| Visualization | Plotly |
| Testing | pytest |

## Development plan

See [ROADMAP.md](ROADMAP.md), [CONTRIBUTING.md](CONTRIBUTING.md), and [docs/RESEARCH_PLAN.md](docs/RESEARCH_PLAN.md).

## Research integrity

- Preserve original datasets; cleaning creates a new version.
- Treat anomalies as review flags, not automatic proof of invalidity.
- Publish scoring weights and component definitions.
- Fit preprocessing only on training data to prevent train/test leakage.
- Record dataset provenance, parameters, random seeds, and limitations.
- Never fabricate benchmark results or test outcomes.

## Security

Validate uploads, enforce file limits, sanitize filenames, and never execute uploaded content. Do not commit secrets, credentials, local databases, or private datasets.

## License

MIT. See [LICENSE](LICENSE).
