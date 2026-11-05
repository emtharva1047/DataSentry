# DataSentry

**An intelligent framework for automated dataset quality assessment, anomaly detection, and machine-learning readiness analysis.**

DataSentry is a research-oriented full-stack application that profiles tabular datasets, detects quality issues using statistical, rule-based, and machine-learning techniques, recommends transparent cleaning actions, and evaluates how data defects affect downstream ML models.

> **Status:** The FastAPI backend supports validated CSV ingestion, SQLite metadata persistence, dataset listing/detail, read-only statistical profiling, inferred quality assessment with an explainable Data Quality Score (DQS), and explicit caller-supplied schema/domain validation. The Next.js dashboard provides API status, dataset metrics, a dataset library, CSV upload, an interactive quality report, and configurable numerical anomaly scans with detector evidence. Frontend lint, TypeScript, and production-build checks are enforced in GitHub Actions. Profile visualization, live browser upload verification, cleaning, ML-readiness, and controlled research evaluation remain in progress.

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

Anomaly review is available beside the quality check for each dataset. The dashboard sends detector selections and validated parameters to `POST /api/datasets/{id}/anomalies`, then displays per-detector flagged counts, row references, numeric eligibility, and method notes. The scan uses all eligible numeric-like columns; column-level filtering remains API-only. Anomaly findings are not included in DQS and never change source rows.

Quality findings are evidence for review, not automatic corrections. The inferred validity detector is conservative; explicit business rules must be supplied rather than guessed. Schema validation is available through the API and is supplemental to the inference-based DQS in this version. Case and whitespace variants are review flags. The endpoint does not mutate or delete source data.

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
