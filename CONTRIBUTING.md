# Contributing to DataSentry

DataSentry prioritizes reproducibility, transparent methods, and small reviewable changes.

## Development setup

Follow the Windows setup instructions in README.md. Keep Python dependencies inside backend/.venv and Node dependencies inside frontend/node_modules.

## Branches and commits

Use focused branches such as feat/csv-upload, feat/quality-scoring, fix/sqlite-session-close, or docs/research-methodology.

Use Conventional Commit-style messages:
- feat: add CSV dataset upload endpoint
- fix: handle empty CSV files safely
- test: cover missing-value profiling
- docs: describe synthetic corruption methodology

Do not create meaningless commits solely to increase the contribution count. Each commit should represent a coherent, reviewable change.

## Code expectations

- Add type hints and input validation.
- Keep route handlers thin; put processing logic in services.
- Add tests for bug fixes and new algorithms.
- Make stochastic behavior reproducible with explicit seeds.
- Keep original datasets immutable.
- Treat anomalies as review flags, not confirmed errors.
- Never commit user datasets, SQLite files, secrets, virtual environments, or node_modules.

## Pull requests

Include the problem, solution, test commands and actual results, screenshots for UI changes, and research assumptions or limitations.
