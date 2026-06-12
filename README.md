# Tube Manager

A playlist-backed saved-video manager with YouTube-style task flows.

## Deploy

- Push this repo to GitHub.
- In Render, create a new Web Service from the repo.
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Add env var `YOUTUBE_API_KEY` in Render if you want API-first mode; otherwise headless fallback is used.

## Notes

- First run should produce a `/health` 200 and `/` HTML page.
- If the UI isn’t modern/modernized yet, replace root route/home in `app.py` with the intended page build step before deploying.
- Keep auto-deploy enabled after confirming the first deploy works.
