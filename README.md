# DataSentry

**An intelligent framework for automated dataset quality assessment, anomaly detection, and machine-learning readiness analysis.**

DataSentry is a research-oriented full-stack application that profiles tabular datasets, detects quality issues using statistical, rule-based, and machine-learning techniques, recommends transparent cleaning actions, and evaluates how data defects affect downstream ML models.

> **Status:** The FastAPI backend supports validated CSV ingestion and dataset metadata APIs. The Next.js dashboard now includes API status, CSV upload, and a dataset library. Automated profiling, quality scoring, anomaly detection, cleaning, ML readiness, and research evaluation remain in progress.

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

### Frontend (Windows PowerShell)
```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000. The dashboard uses the FastAPI service at http://127.0.0.1:8000 by default. Change `NEXT_PUBLIC_API_BASE_URL` in `.env.local` when the backend runs elsewhere.

Available frontend checks:
```powershell
npm run lint
npm run typecheck
npm run build
```

Node.js 20.9 or newer is required (Node.js 22 LTS is recommended). See [frontend/README.md](frontend/README.md) for the complete setup guide.

## Research integrity and security
Preserve originals; cleaning creates a new version. Anomaly flags are not proof of invalid data. Fit preprocessing only on training data. Record dataset provenance, configurations, random seeds, and limitations. Do not fabricate research results. Validate uploads, sanitize filenames, never execute user files, and do not commit secrets or private datasets.

See [docs/ROADMAP.md](docs/ROADMAP.md), [docs/RESEARCH_PLAN.md](docs/RESEARCH_PLAN.md), and [CONTRIBUTING.md](CONTRIBUTING.md).

## License
MIT.
