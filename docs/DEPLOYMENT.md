# Deployment and Operational Readiness

**Status:** deployment guidance for a research prototype; not a production-security certification.

## Supported deployment shape

The current persistence layer is SQLite plus generated CSV files. Use one API instance, one Uvicorn worker, and one persistent writable data volume. Do not run multiple API replicas against separate local disks or assume SQLite on a network filesystem is a supported distributed database.

The configured data root contains:

- `datasentry.db` — SQLAlchemy SQLite database.
- `uploads/` — immutable original CSV uploads.
- `versions/` — derived immutable cleaning versions.

Set `DATASENTRY_DATA_DIR` before the Python process starts. The application resolves this setting during module import; changing the environment of an already-running process does not relocate its open database engine or storage paths. Use an absolute path on a persistent volume, grant the service account read/write access, and keep the directory outside the source checkout.

Example:

```sh
export DATASENTRY_DATA_DIR=/var/lib/datasentry
export DATASENTRY_CORS_ORIGINS=https://datasentry.example.com
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

The API currently uses SQLite and a local filesystem; the example is a single-instance prototype deployment, not a horizontally scalable topology.

## API CORS allowlist

Configure `DATASENTRY_CORS_ORIGINS` as a comma-separated list of exact browser origins, including scheme and optional non-default port:

```sh
DATASENTRY_CORS_ORIGINS=https://datasentry.example.com,https://staging.datasentry.example.com
```

When the variable is unset, the API retains the development defaults `http://localhost:3000` and `http://127.0.0.1:3000`. When it is set, every entry is validated at API import/startup. Only HTTP and HTTPS origins are accepted. Wildcards, the opaque `null` origin, credentials, paths, queries, fragments, malformed hosts/ports, and empty entries are rejected. A single trailing slash and default HTTP/HTTPS ports are normalized; duplicate origins are removed. Invalid configuration raises a startup error rather than silently falling back to a broader allowlist.

Set the variable before starting or restarting FastAPI. CORS is a browser policy, **not authentication or authorization**; non-browser clients can call the API regardless of CORS headers.

## Frontend API URL

The browser bundle reads `NEXT_PUBLIC_API_BASE_URL` at Next.js build time. Set it to the public API origin before building the frontend, without an API path suffix:

```sh
export NEXT_PUBLIC_API_BASE_URL=https://api.datasentry.example.com
cd frontend
npm ci
npm run lint
npm run typecheck
npm run build
npm run start -- --hostname 0.0.0.0 --port 3000
```

Changing this public variable after `npm run build` does not rewrite the existing browser bundle; rebuild and redeploy the frontend. The backend CORS list must include the exact frontend origin, not the API origin, for example `https://datasentry.example.com`.

## TLS, reverse proxy, and network boundary

Terminate TLS at a maintained reverse proxy or platform ingress. Expose only HTTPS to browsers, forward requests to the private API listener, and restrict direct access to the API port. Configure proxy upload-body limits consistently with the application's 10 MiB CSV upload limit. Do not treat the CORS allowlist as a network boundary.

**Current security limitation:** this prototype has no user authentication, authorization, tenant isolation, or API rate limiting. Upload, profiling, anomaly detection, and model endpoints can consume CPU, memory, disk, and database resources. Keep the service behind an authenticated VPN, private network, or trusted ingress with access controls until application-level identity, authorization, abuse controls, and operational monitoring are implemented and tested. Do not expose an unauthenticated instance directly to the public internet or upload sensitive/private datasets.

## Health and readiness checks

- `GET /api/health` confirms that the FastAPI process responds; it does not query SQLite.
- `GET /api/overview` queries the database and reports the connection state and dataset count. Use this as the database-readiness smoke check.
- `GET /docs` exposes the interactive API schema; restrict it at the ingress if the deployment policy requires it.

After deployment, verify the frontend can load the overview endpoint from its configured origin and that the browser console contains no CORS errors. Run the isolated API demo in a separate test process, not against the production data root:

```sh
cd backend
python -m scripts.run_end_to_end_demo
pytest -q tests/test_end_to_end_demo.py
```

The API demo uses in-memory SQLite and temporary upload/version directories. The full browser journey remains the separate Playwright CI workflow.

## Backups and recovery

There is no automated backup/restore subsystem in this prototype. Back up the SQLite database and both file directories as one coordinated recovery set. Quiesce writes or stop the API while taking a filesystem snapshot so the database metadata and referenced CSV files represent the same point in time. Store backups outside the runtime data volume, restrict access, encrypt them according to the deployment environment, and periodically rehearse restoration into a separate data root.

Do not commit `datasentry.db`, uploaded datasets, derived versions, environment files, credentials, or backup archives to Git. The repository's ignore rules cover the normal local database, upload/version directories, and environment files; verify the actual configured data root is also excluded from any backup-to-repository process.

## Operational limitations and release gate

Before considering a deployment suitable for real users, the following remain required:

- Application authentication and role/tenant authorization.
- API rate limiting, upload quotas, request timeouts, and resource limits for expensive profiling/detector/model requests.
- Automated, coordinated backups and a tested restore procedure.
- Centralized logs, metrics, alerting, disk-space monitoring, and retention policy.
- A production database/storage architecture if multiple API instances or higher write concurrency are needed.
- Dependency vulnerability review and a repeatable lockfile/dependency pinning strategy for Python.
- A deployment-specific threat model and security review.

The current prototype is suitable for controlled evaluation and demonstration in a trusted environment. Passing CI and browser tests does not establish production readiness, high availability, regulatory compliance, or security against hostile uploads/users.
