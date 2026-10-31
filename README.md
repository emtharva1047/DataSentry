# DataSentry

**An intelligent framework for automated dataset quality assessment, anomaly detection, and machine-learning readiness analysis.**

DataSentry is a research-oriented full-stack application that profiles tabular datasets, detects quality issues using statistical, rule-based, and machine-learning techniques, recommends transparent cleaning actions, and evaluates how data defects affect downstream ML models.

> **Status:** Early development. The backend supports validated CSV ingestion, SQLite metadata persistence, dataset listing, and dataset detail retrieval. Browser upload UI, profiling, detection, cleaning, and research experiments remain in progress.

## Planned capabilities
- CSV upload with extension/header validation, UTF-8/Windows-1252 decoding, byte/row/column limits, generated storage names, SHA-256 fingerprints, and metadata persistence.
- Dataset list/detail APIs that never expose internal storage paths.
- Automated profiling, rule-based checks, IQR/robust-Z/Isolation-Forest detection, explainable DQS, cleaning previews, ML readiness, and reproducible corruption experiments.

## Technology
Next.js, React, TypeScript, Tailwind CSS, Python 3.12, FastAPI, SQLAlchemy, SQLite, Pandas, NumPy, SciPy, scikit-learn, and Plotly.

## Dataset API
- `POST /api/datasets/upload` — multipart CSV upload, response contains safe metadata.
- `GET /api/datasets` — list dataset metadata.
- `GET /api/datasets/{id}` — retrieve one dataset.
- `GET /api/health` and `GET /api/overview` — service and database status.

Initial backend limits: 10 MiB, 100,000 data rows, and 200 columns. Uploaded files use generated UUID storage names; originals are not modified.

## Local setup
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

### Frontend
Generate the Next.js App Router project using TypeScript, ESLint, Tailwind CSS, `src/`, and App Router. Copy `frontend-snippets/page.tsx` to `frontend/src/app/page.tsx`, copy `.env.local.example` to `.env.local`, then run `npm run dev`.

## Research integrity and security
Preserve originals; cleaning creates a new version. Anomaly flags are not proof of invalid data. Fit preprocessing only on training data. Record dataset provenance, configurations, random seeds, and limitations. Do not fabricate research results. Validate uploads, sanitize filenames, never execute user files, and do not commit secrets or private datasets.

See [docs/ROADMAP.md](docs/ROADMAP.md), [docs/RESEARCH_PLAN.md](docs/RESEARCH_PLAN.md), and [CONTRIBUTING.md](CONTRIBUTING.md).

## License
MIT.
