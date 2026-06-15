# Deployment

## Target
Oracle Cloud Infrastructure (OCI) compute instance (e.g., ARM Ampere or x86).

## Prerequisites
- `git`, `python3.11+`, `uv` or `pip`
- Optional: `docker` + `docker compose` if using containers
- Open ports: `8000` (API) and optionally `80`/`443` behind reverse proxy

## Option A — systemd service (bare metal)
1. Clone repo to `/opt/tube-manager`
2. Create venv and install deps
3. Install systemd unit `tube-manager.service`
4. Enable and start

See `docs/deployment/systemd/tube-manager.service`.

## Option B — Docker
Build and run with `Dockerfile` + `docker compose`.

See `docs/deployment/docker-compose.yml`.

## Reverse proxy (recommended)
- nginx or Caddy on port 80/443
- Tunnel target should be the Oracle public IP: `161.115.18.209:8000`
- Public endpoint example: `https://<subdomain>.ngrok-free.app -> http://161.115.18.209:8000`
- Terminate TLS with Let's Encrypt if public access is required

## Env/config
- Copy `config.example.yaml` to `config.yaml` and set `storage.path`
- Do not commit secrets
