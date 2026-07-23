"""Runbook

Local dev:
1. `python -m venv .venv`
2. `.venv/Scripts/activate`
3. `pip install -r requirements.txt` (or `pyproject.toml`)
4. `python -m tube_manager.cli` or `uvicorn --app-dir . tube_manager.api:app --reload`

Conventions:
- local paths resolve under `C:\Users\davem\repos\tube-manager`
- tests run with `pytest`
- docs are under `docs/`