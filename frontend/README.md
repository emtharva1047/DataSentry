# DataSentry frontend

Next.js App Router dashboard for the DataSentry FastAPI service.

## Requirements

- Node.js 20.9 or newer (Node.js 22 LTS recommended)
- npm
- The DataSentry backend running locally

## Run locally (Windows PowerShell)

In one terminal, start the backend:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH = "."
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal, start the frontend:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000. The default API URL is http://127.0.0.1:8000.
For a different backend URL, edit `NEXT_PUBLIC_API_BASE_URL` in `.env.local` and restart the frontend.

## Available commands

- `npm run dev` — development server
- `npm run lint` — ESLint
- `npm run typecheck` — TypeScript checks
- `npm run build` — production build

The dashboard implements API connection status, dataset counts, dataset listing, validated CSV upload, an interactive DQS report, and numerical anomaly review. For each dataset, run a quality check or anomaly scan. The anomaly panel supports IQR, modified robust Z-score, and Isolation Forest with configurable parameters, bounded row evidence, numeric-column eligibility diagnostics, and reproducibility details. Start the FastAPI backend locally before using the dashboard.
