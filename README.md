# DataSentry

**An intelligent framework for automated dataset quality assessment, anomaly detection, and machine-learning readiness analysis.**

DataSentry is a research-oriented full-stack application that profiles tabular datasets, detects quality issues using statistical, rule-based, and machine-learning techniques, recommends transparent cleaning actions, and evaluates how data defects affect downstream ML models.

> **Status:** The FastAPI backend supports validated CSV ingestion, SQLite metadata persistence, statistical profiling, explainable quality assessment, explicit schema/domain validation, anomaly detection, safe cleaning, immutable versions, and DQS/numeric-profile comparison. The Next.js dashboard integrates quality reports, anomaly review, cleaning previews, explicit apply, version history, and before/after comparisons. Live browser-to-API verification, baseline model dashboard integration, repeated-seed model evaluation, and controlled research evaluation remain in progress. ML-readiness diagnostics and seeded baseline model APIs are implemented. Deterministic synthetic-corruption and metric-aggregation research primitives are implemented; detector-specific evaluation remains in progress.

## Current capabilities

- CSV upload with extension/header validation, UTF-8/Windows-1252 decoding, byte/row/column limits, generated storage names, SHA-256 fingerprints, and metadata persistence.
- Dataset list/detail APIs that never expose internal storage paths.
- Read-only dataset profiling: inferred column types, missingness, unique counts, numeric summaries, categorical frequencies, numeric histograms, and Pearson correlations (up to 20 numeric columns).
- Read-only inferred quality assessment for missing values, exact duplicate rows, likely numeric type mismatches, and categorical whitespace/case variants.
- Explicit schema/domain validation for expected columns, required values, string/integer/number/boolean types, inclusive numeric ranges, allowed-value sets, and unexpected columns.
- Explainable DQS with completeness (30%), validity (30%), uniqueness (20%), and consistency (20%); inapplicable components are excluded and active weights are renormalized.
- Browser workspace with API status, dataset listing, CSV upload, upload feedback, and refresh.
- Interactive quality report viewer with overall DQS, component numerators/denominators, severity counts, issue evidence, and detector notes.
- Interactive numerical anomaly review with IQR, modified robust Z-score, and Isolation Forest selection; configurable thresholds, contamination, random seed, and tree count; numeric-column eligibility diagnostics; flagged-row evidence; and source fingerprint display.
- Interactive safe-cleaning workflow with advisory recommendations, explicit operation selection, read-only before/after row previews, a review acknowledgement before apply, immutable version history, and DQS/numeric-profile comparison.
- Read-only ML-readiness diagnostics for target completeness, classification imbalance, suspicious target copies/associations, duplicate feature-vector split risks, feature redundancy, missing feature values, and dataset-size caveats; seeded logistic-regression and Ridge baseline evaluation with train-only preprocessing.
- Internal deterministic synthetic-corruption utilities for missingness, exact duplicate insertion, categorical inconsistency, invalid numeric values, and numerical anomalies, with exact cell/row labels; binary detector metrics and a three-or-more-seed mean/sample-standard-deviation aggregator.

Anomaly review is available beside the quality check for each dataset. The dashboard sends detector selections and validated parameters to `POST /api/datasets/{id}/anomalies`, then displays per-detector flagged counts, row references, numeric eligibility, and method notes. The scan uses all eligible numeric-like columns; column-level filtering remains API-only. Anomaly findings are not included in DQS and never change source rows.

Quality findings are evidence for review, not automatic corrections. The inferred validity detector is conservative; explicit business rules must be supplied rather than guessed. Schema validation is available through the API and is supplemental to the inference-based DQS in this version. Case and whitespace variants are review flags. The endpoint does not mutate or delete source data.

## Version quality comparison

When a derived version is selected in the cleaning workspace, DataSentry recalculates the original upload and selected version with the same inference-based DQS rules. The response includes overall and component-level score deltas, applicability, issue counts, row/column counts, and SHA-256 fingerprints. A positive DQS delta indicates a higher score under this rule-based definition; it is not proof of improved downstream model performance. If component applicability changes, the active-weight denominator also changes and must be considered. Numeric comparison now includes before/after numeric summaries, aligned 10-bin histograms, and pairwise Pearson correlation deltas for up to 20 numeric columns. Histograms use shared per-column bin edges when a column is numeric in both versions; correlation deltas are omitted when either correlation is undefined. Categorical frequency comparisons remain out of scope.

## Technology

- Frontend: Next.js App Router, React, TypeScript, Tailwind CSS.
- Backend: Python 3.12, FastAPI, SQLAlchemy, SQLite.
- Data science: Pandas, NumPy, SciPy, scikit-learn; Plotly for planned visual reporting.

## Dataset API

- `POST /api/datasets/upload` — multipart CSV upload; response contains safe metadata.
- `GET /api/datasets` — list dataset metadata.
- `GET /api/datasets/{id}` — retrieve one dataset.
- `GET /api/datasets/{id}/profile` — generate a read-only statistical profile on demand.
- `GET /api/datasets/{id}/quality` — generate inferred rule-based issue evidence and an explainable DQS on demand.
- `POST /api/datasets/{id}/quality/validate` — validate against a caller-supplied schema/domain contract.
- `POST /api/datasets/{id}/anomalies` — run selected read-only numerical anomaly detectors with reproducible parameters.
- `GET /api/datasets/{id}/cleaning/recommendations` — return advisory, non-executing cleaning suggestions.
- `POST /api/datasets/{id}/cleaning/preview` — preview explicitly selected operations without writing a version.
- `POST /api/datasets/{id}/cleaning/apply` — apply selected operations into a new immutable version.
- `GET /api/datasets/{id}/cleaning/versions` — list derived versions and their parent lineage.
- `GET /api/datasets/{id}/cleaning/versions/{version_id}/quality-comparison` — recalculate original and selected version DQS and compare numeric summaries, shared-bin histograms, and defined Pearson correlation pairs.
- `POST /api/datasets/{id}/ml-readiness` — deterministic target, class-balance, leakage-heuristic, duplicate-split, redundancy, and sample-size diagnostics; does not fit a model.
- `POST /api/datasets/{id}/baseline-model` — fit a seeded logistic-regression classifier or Ridge regressor using a holdout split and preprocessing fitted only on training rows.
- `GET /api/health` and `GET /api/overview` — service and database status.

### Explicit schema validation

Submit a JSON body to `POST /api/datasets/{id}/quality/validate`:

```json
{
  "columns": {
    "age": {
      "type": "integer",
      "required": true,
      "minimum": 0,
      "maximum": 120
    },
    "status": {
      "type": "string",
      "allowed_values": ["active", "inactive"],
      "case_sensitive": false
    },
    "enabled": {
      "type": "boolean"
    }
  },
  "allow_extra_columns": false
}
```

Supported types are `string`, `integer`, `number`, and `boolean`. Integer values must be finite whole numbers; number values must be finite. Boolean parsing accepts true/false, 1/0, and yes/no (case-insensitive, surrounding whitespace ignored). Numeric minimum and maximum bounds are inclusive and apply only to integer/number columns. Allowed values are exact by default; case-insensitive matching is opt-in and does not trim whitespace. Missing expected columns, missing required cells, type mismatches, range violations, disallowed values, and unexpected columns are returned as separate findings with affected counts, severity, and bounded one-based data-row evidence.

The schema request is validated before the CSV is read. Unknown schema fields, empty schema names, more than 200 expected columns, empty allowed-value lists, and contradictory numeric bounds are rejected with HTTP 422. A dataset that does not exist returns 404; a stored source file that is missing or unsafe returns 410. Validation is read-only: the uploaded bytes and SHA-256 fingerprint remain unchanged. These schema findings are supplemental to the inference-based DQS and do not change its component scores in this version.

### Quality assessment method

The DQS components are each scored from 0–100 with explicit numerators and denominators:

- Completeness: non-missing cells / all cells.
- Validity: finite, parseable values / non-missing values in inferred numeric-like columns. A column is considered numeric-like when at least 80% of its non-missing values parse as finite numbers and at least two values are valid.
- Uniqueness: rows excluding duplicate occurrences after the first / all rows.
- Consistency: categorical values without detected surrounding whitespace or case-only variants / non-missing categorical values.

The nominal weights are 30%, 30%, 20%, and 20%. If a component has no assessable denominator, it is marked inapplicable and the remaining weights are renormalized. The overall score is a weighted mean of applicable components. The report includes component numerators, denominators, active weights, issue severity, affected counts, and one-based data-row evidence (excluding the header).

Severity is high at an affected rate of at least 20%, medium at 5% to below 20%, and low below 5%. Exact duplicate detection counts repeated occurrences after the first. Missing-value behavior follows pandas CSV parsing defaults. The numeric type check is not a substitute for business-domain validation; no arbitrary value ranges are inferred. Anomaly flags are separate from DQS.

Initial backend upload limits: 10 MiB, 100,000 data rows, and 200 columns. Uploaded files use generated UUID storage names; originals are not modified. Profiles and quality reports are computed on request and are not persisted as separate records.

## Safe cleaning and immutable versions

Cleaning is explicit and versioned. The recommendation endpoint never changes data. A preview is read-only and returns bounded before/after row evidence. Only a separate apply request writes a new generated CSV under the backend version directory and records an immutable version in SQLite. The original upload and earlier versions are retained.

Example preview or apply request:

```json
{
  "base_version_id": null,
  "drop_exact_duplicates": true,
  "fill_numeric_median": ["amount"],
  "fill_categorical_mode": ["city"],
  "trim_whitespace": ["city"],
  "lowercase_categories": []
}
```

Supported operations are exact duplicate removal (first occurrence retained), median imputation for finite numeric columns, mode imputation for categorical columns, whitespace trimming, and explicitly requested lower-case normalization. Numeric imputation rejects columns containing non-numeric or non-finite observed values. Mode ties use the first value returned by pandas mode ordering. Lower-case normalization is marked high risk because case can be semantically meaningful.

Use base_version_id to branch from a prior immutable version; omit it or set it to null to start from the original upload. Each successful apply receives a monotonically increasing per-dataset version number and records its parent, operation manifest, row/column counts, file size, and SHA-256. Storage paths are never returned. A valid operation that produces no changes returns HTTP 409 and creates no version. Preview evidence is capped at ten changed rows and ten cells per row. These operations are deterministic for a fixed input and request, but imputation choices are statistical assumptions and must be reviewed before applying.

### Dashboard cleaning workflow

Open the dataset library and choose **Review cleaning** for a dataset. Select the original upload or a previously created immutable version as the base. Recommendations are advisory; choose only operations justified by the dataset context. Generate a read-only preview, inspect row counts and bounded before/after cell evidence, acknowledge the preview, and then explicitly create a new version. The dashboard refreshes the version history and selects the new version as the next base. The original upload and prior versions are retained.

The dashboard compares row counts, sampled cell changes, DQS components, numeric summaries, aligned histograms, and defined Pearson correlation pairs for up to 20 numeric columns. Categorical frequency distributions are not yet compared, and live browser-to-FastAPI workflow verification remains pending. Lowercase normalization remains high-risk and is not selected by default.


## Baseline model evaluation

Submit a JSON body to `POST /api/datasets/{id}/baseline-model`:

```json
{
  "target_column": "outcome",
  "task_type": "classification",
  "feature_columns": ["age", "region", "income"],
  "test_size": 0.25,
  "random_state": 42
}
```

`feature_columns` is optional; when omitted, every column except the target is selected. The target is required and must not also appear as a feature. The test fraction must be greater than 0.1 and less than 0.5. At least 10 rows with usable target values are required. Classification requires at least two classes, at least two observations per class, and enough rows to place every class in both partitions. Regression excludes missing, non-numeric, and non-finite target labels before splitting.

The classification baseline is class-weighted logistic regression. The regression baseline is Ridge regression. Numeric feature types are inferred from the training partition only using at least two finite values and 80% parseability among observed training values. The train/test split is created before this inference. Median imputation and standard scaling for numeric features, and constant missing-value imputation plus one-hot encoding for categorical features, are fitted inside a scikit-learn Pipeline using training rows only. Unseen test categories are ignored by the fitted encoder.

Classification metrics include accuracy, balanced accuracy, macro precision/recall/F1, confusion counts, and binary ROC AUC when applicable. Regression metrics include MAE, RMSE, and R². The response records split seed, test fraction, train/test counts, inferred feature types, preprocessing fit scope, runtime, source SHA-256, and pandas/NumPy/scikit-learn versions. No model artifact is persisted and the source CSV is never modified.

This is a single seeded holdout baseline, not model selection or a performance guarantee. Random row splitting does not prevent duplicate entities or feature vectors crossing partitions; inspect the ML-readiness report and use group-aware splitting when appropriate. Small datasets and single-split metrics have high uncertainty. Repeat with at least three seeds and report mean and standard deviation before making research claims. The untouched-test-set corruption experiment remains a separate research milestone.

## Controlled research utilities

The backend research module app.services.dataset_research provides in-memory experiment construction; these are not public API endpoints and do not persist corrupted datasets.

- inject_synthetic_corruption(frame, rate, seed, defects) returns a separate corrupted DataFrame and exact ground-truth labels for missing cells, inserted duplicate rows, categorical case/whitespace variants, invalid numeric tokens, and injected numerical extremes.
- The rate is applied to the currently eligible cells for cell-level defects and eligible source rows for duplicate insertion. Counts are rounded up to at least one when candidates exist. The seed is a 32-bit unsigned integer.
- Ground truth distinguishes zero-based positions in the returned corrupted frame from one-based data-row numbers. Duplicate labels identify only the newly appended row and retain its source-row reference. Cell labels identify each injected cell and defect type.
- Ineligible defect types are reported as skipped with a reason; the generator does not invent labels. The input DataFrame is never modified.
- evaluate_binary_detector returns precision, recall, F1, accuracy, and TP/FP/TN/FN counts. Undefined precision/recall/F1 denominators use an explicit zero convention.
- aggregate_seed_metrics requires at least three distinct seeds and identical finite numeric metric names across runs. It reports the arithmetic mean and sample standard deviation (ddof=1).

These are experiment primitives, not experimental results. Detector-specific predictions, runtime/memory benchmarks, repeated-seed detector runs, and the clean untouched-test downstream ML experiment remain to be executed. Synthetic corruption rates are controlled settings, not estimates of real-world defect prevalence.

## Local setup

Run the backend and frontend in separate terminals.

### Backend (Windows PowerShell)

```powershell
cd backend
py -3.12 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH = "."
pytest -q
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend (Windows PowerShell)

```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`. The frontend defaults to `http://127.0.0.1:8000`; override `NEXT_PUBLIC_API_BASE_URL` in `.env.local` if the API uses another address. The backend CORS allowlist permits the default localhost frontend origins.

Frontend checks:

```powershell
npm run lint
npm run typecheck
npm run build
```

## Research integrity and security

Preserve originals; cleaning creates a new version. Anomaly flags are not proof of invalid data. Fit preprocessing only on training data. Record dataset provenance, configurations, random seeds, software versions, and limitations. Do not fabricate research results. Validate uploads, sanitize filenames, never execute user files, and do not commit secrets or private datasets.

See [docs/ROADMAP.md](docs/ROADMAP.md), [docs/RESEARCH_PLAN.md](docs/RESEARCH_PLAN.md), and [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT.
