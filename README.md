# Tube Manager

A playlist-backed saved-video manager with YouTube-style task flows.

## Repo layout
- `tube_manager/` — app source package
- `tests/` — test suite
- `docs/` — architecture notes, runbook, and usage guides

## Runbook

### API
[Install dependencies](#install-dependencies), then:

```bash
uvicorn --app-dir . tube_manager.api:api --reload
```

Open:
- docs: http://127.0.0.1:8000/docs
- health: http://127.0.0.1:8000/tasks

### CLI
```bash
python -m tube_manager.cli list
python -m tube_manager.cli add "Demo" --type generic --priority high
python -m tube_manager.cli run <id>
python -m tube_manager.cli remove <id>
```

### Install dependencies
```bash
pip install -r requirements.txt
```

Python 3.11+ recommended.
