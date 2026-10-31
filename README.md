# DataSentry

**An intelligent framework for automated dataset quality assessment, anomaly detection, and machine-learning readiness analysis.**

DataSentry is a research-oriented full-stack application that profiles tabular datasets, detects quality issues using statistical, rule-based, and machine-learning techniques, recommends transparent cleaning actions, and evaluates how data defects affect downstream ML models.

> **Status:** The FastAPI backend supports validated CSV ingestion, SQLite metadata persistence, dataset listing/detail, and a read-only statistical profiling endpoint. The Next.js dashboard provides API status, dataset metrics, a dataset library, and CSV upload. Frontend lint, TypeScript, and production-build checks pass in GitHub Actions. Live browser upload verification and quality-rule, cleaning, ML-readiness, and research modules remain in progress.

## Current capabilities

- CSV upload with extension/header validation, UTF-8/Windows-1252 decoding, byte/row/column limits, generated storage names, SHA-256 fingerprints, and metadata persistence.
- Dataset list/detail APIs that never expose internal storage paths.
- Read-only dataset profiling: inferred column types, missingness, unique counts, numeric summaries, categorical frequencies, numeric histograms, and Pearson correlations (up to 20 numeric columns).
- Browser workspace with API status, dataset listing, CSV upload, upload feedback, and refresh.
- Rule-based quality checks, explainable DQS, anomaly detection, cleaning previews, ML readiness, and reproducible corruption experiments are planned next.

## Technology

- Frontend: Next.js App Router, React, TypeScript, Tailwind CSS.
- Backend: Python 3.12, FastAPI, SQLAlchemy, SQLite.
- Data science: Pandas, NumPy, SciPy, scikit-learn; Plotly for planned visual reporting.

## Dataset API

- `POST /api/datasets/upload` — multipart CSV upload; response contains safe metadata.
- `GET /api/datasets` — list dataset metadata.
- `GET /api/datasets/{id}` — retrieve one dataset.
- `GET /api/datasets/{id}/profile` — generate a read-only statistical profile on demand.
- `GET /api/health` and `GET /api/overview` — service and database status.

Initial backend limits: 10 MiB, 100,000 data rows, and 200 columns. Uploaded files use generated UUID storage names; originals are not modified. Profiles are computed on request and are not persisted as separate records yet.

## Local setup

Run the backend and frontend in separate terminals.

### Backend (Windows PowerShell)

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
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
