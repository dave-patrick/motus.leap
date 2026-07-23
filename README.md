# motus.leap

An automated agent for managing YT playlists using browser automation and OAuth APIs. This is part of the motus.leap suite and can be easily integrated into other AI systems.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

<h2 align="center">Automated YouTube Playlist Orchestrator</h2>

<p align="center">
  <a href="https://github.com/dave-patrick/motus.leap/issues">Report Bug</a> &nbsp;|&nbsp;
  <a href="https://github.com/dave-patrick/motus.leap/discussions">Request Feature</a>
</p>

---

## ✨ Features

### Core
- 🎬 **YouTube Data API v3** — Real-time playlist & subscription management  
- 🔗 **Channel-to-Playlist Mappings** — Auto-route videos by channel  
- 🤖 **AI Classification** — LLM-powered video categorization  
- 📊 **Full Cluster Scan** — Deep YouTube account analysis  

### Advanced
- 📦 **Bulk Operations** — Move, delete, and tag videos in batches  
- 👥 **Multi-User RBAC** — Admin / User / Viewer roles  
- 🔒 **Enterprise Security** — CSP, rate limiting, XSS sanitization  
- ⚡ **Performance** — In-memory caching, connection pooling, async I/O  

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Chromium browser (installed automatically via Playwright)

### Install

```bash
git clone https://github.com/dave-patrick/motus.leap.git
cd motus.leap
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### Run Server

```bash
python server.py
```

Then open `http://localhost:8000`.

---

## 📄 License

MIT — see [LICENSE](LICENSE)

