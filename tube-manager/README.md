# motus.leap

An **Automated YouTube Playlist Orchestrator** — a modern FastAPI web app for organizing YouTube playlists, subscriptions, and video viewing sessions with AI-powered classification, bulk operations, and a responsive mobile-first UI.

## Live Demo

https://tubemanager.onrender.com

## Features

- **YouTube Integration** — Connect via Google OAuth to manage playlists, subscriptions, and Watch Later
- **AI Classification** — Auto-classify videos into playlists using OpenAI, Anthropic, Groq, or custom LLM endpoints
- **Bulk Operations** — Move, delete, tag, import, and export videos in batches (up to 500 per batch)
- **Smart Sync** — Auto-sync Watch Later to playlists based on channel mapping rules
- **Duplicate & Misplaced Detection** — Scan for duplicate videos across playlists and misplaced videos that don't match your mapping rules
- **Background Worker** — Long-running tasks processed asynchronously with retry logic and progress reporting
- **Responsive Design** — Mobile-first UI with touch-optimized controls, PWA support, and offline caching
- **Security** — JWT auth with token rotation, hashed session storage, CORS, rate limiting, and HSTS

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.13) |
| Frontend | Vanilla JS + Tailwind CSS (CDN) |
| Auth | JWT + Google OAuth 2.0 |
| Storage | File-backed (JSON) with LRU caching + disk persistence |
| AI | OpenAI / Anthropic / Groq / Custom endpoints |
| Deploy | Render (auto-deploy from main) |

## Quick Start

```bash
git clone https://github.com/dave-patrick/motus.leap.git
cd motus.leap/tube-manager

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp env.example .env   # Add YOUTUBE_API_KEY, GOOGLE_OAUTH_CLIENT_ID, etc.
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Visit http://localhost:8000

## Deploy to Render

1. Fork this repo
2. Create a **Web Service** on [Render](https://render.com)
   - Root Directory: `tube-manager`
   - Build: `pip install --no-cache-dir -r requirements.txt`
   - Start: `uvicorn app:app --host 0.0.0.0 --port $PORT`
3. Environment variables:
   ```
   TUBE_MANAGER_SECRET_KEY=<random-32+-chars>
   GOOGLE_OAUTH_CLIENT_ID=<your-client-id>
   GOOGLE_OAUTH_CLIENT_SECRET=<your-client-secret>
   GOOGLE_OAUTH_REDIRECT_URI=https://<your-app>.onrender.com/api/auth/google/callback
   ```
4. Attach a persistent disk (1GB+) mounted at `/app/data` for user sessions and config

## Health Check

```
GET /api/health → {"status": "ok", "version": "..."}
```

## Architecture

```
tube-manager/
├── app.py                    # FastAPI entry + static file serving (1864 lines)
├── api/
│   ├── auth.py               # JWT auth, Google OAuth, sessions, users
│   ├── bulk_operations.py    # Bulk move/delete/tag/import/export
│   ├── bulk_operations_impl.py
│   ├── config.py             # Config management endpoints
│   ├── mappings.py           # Channel→playlist mapping CRUD
│   ├── youtube.py            # YouTube API proxy
│   └── websocket.py          # WebSocket terminal
├── services/
│   ├── youtube_service.py    # YouTube client with aggressive LRU caching
│   ├── background_worker.py  # Async task processor with retry
│   ├── ai_classifier.py      # AI video classification + suggestion engine
│   └── youtube_client.py     # Shared httpx YouTube API client
├── core/
│   ├── lru_cache.py          # Async LRU cache with TTL + max_age cleanup
│   ├── http_client.py        # HTTP connection pooling
│   ├── config_manager.py     # Config persistence
│   ├── security.py           # CSP, rate limiting, XSS protection
│   └── limiter.py            # SlowAPI rate limiter
├── models/
│   ├── config.py             # Pydantic config models
│   ├── task.py               # Background task models
│   └── mapping.py            # Channel mapping models
├── web/
│   ├── dashboard.html        # Main dashboard
│   ├── playlists.html        # Playlist management
│   ├── subscriptions.html    # Subscription management
│   ├── settings.html         # OAuth + AI + app settings
│   ├── watch-later.html      # Watch Later sync
│   ├── bulk.html             # Bulk operations UI
│   ├── maintenance.html      # Maintenance queue
│   ├── auth.html             # OAuth callback landing
│   ├── playlist.html         # Playlist detail
│   ├── roadmap.html          # Project roadmap
│   └── static/
│       ├── dashboard.js      # Main dashboard JS
│       ├── playlists.js      # Playlist management JS
│       ├── subscriptions.js  # Subscription management JS
│       ├── auth-check.js     # Auth status checker
│       ├── ux-enhancements.js # SPA router + keyboard shortcuts
│       ├── sw.js             # Service worker (PWA)
│       └── manifest.json     # PWA manifest
├── tests/
│   ├── unit/                 # Unit tests (YouTube service, cache, bug fixes)
│   ├── integration/          # Integration tests (API endpoints)
│   ├── security/             # Security tests (CSP, auth, rate limiting)
│   └── load/                 # Load/performance tests
├── CLAUDE.md                 # Project context for AI agents
└── requirements.txt
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login (returns JWT + cookie) |
| GET | `/api/auth/google` | Initiate Google OAuth |
| GET | `/api/playlists` | List user playlists |
| GET | `/api/youtube/fetch-all` | Fetch all YouTube data |
| GET | `/api/youtube/videos` | Get videos with duration |
| GET | `/api/watch-later` | List Watch Later items |
| POST | `/api/watch-later/move` | Move videos to playlist |
| GET | `/api/subscriptions` | List subscriptions |
| POST | `/api/subscriptions/subscribe` | Subscribe to channel |
| GET | `/api/mappings` | Get channel→playlist mappings |
| POST | `/api/mappings` | Create/update mapping |
| POST | `/api/ai/classify` | AI classify a video |
| GET | `/api/ai/suggestions` | Get AI mapping suggestions |
| POST | `/api/bulk/move` | Bulk move videos |
| POST | `/api/bulk/delete` | Bulk delete videos |
| POST | `/api/bulk/import` | Import playlists |
| GET | `/api/stats` | Dashboard statistics |
| POST | `/api/action` | Dispatch background task |
| GET | `/api/diagnostics/youtube` | YouTube API connectivity |

## Recent Updates (June 2027)

- **Mobile-first responsive design** — All pages optimized for mobile with 44px+ touch targets
- **PWA support** — Service worker + manifest for offline caching
- **Security hardening** — Token rotation, HSTS, video ID validation, gzip compression
- **Performance** — LRU cache cleanup, async file I/O, consolidated polling
- **UX improvements** — Fetch retry with backoff, pull-to-refresh, skeleton loaders
- **Code quality** — Single FastAPI instance, consistent error handling, comprehensive test coverage

## License

MIT
