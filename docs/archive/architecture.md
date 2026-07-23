# Architecture notes

## Layout
- `tube_manager/` — app package: config, storage, runner.
- `tests/` — pytest harness for core behavior.
- `config.example.yaml` — non-sensitive local config template.

## Design
- Config is YAML-only.
- Storage is file-backed by default.
- Runner is thread-based and returns strict task status.

## Next steps
- Replace the storage backend with a richer implementation.
- Add typed task schemas.
- Wire integrations with local secrets only at runtime.
