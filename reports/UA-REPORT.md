# motus.leap — Understand-Anything Report

- **Languages**: bak, css, dockerfile, html, javascript, markdown, python, shell, toml, txt, unknown, yaml
- **Frameworks**: Docker, FastAPI, GitHub Actions, Google API Python Client, HTTPX, Passlib, PyJWT, PyYAML, Pydantic, Pytest, Render, SlowAPI, Uvicorn, aiofiles, python-jose
- **Description**: motus.leap is an Automated YouTube Playlist Orchestrator built with FastAPI for managing YouTube playlists, subscriptions, and video organization. It provides automated playlist management with intelligent channel-to-playlist mappings, AI-powered video classification, and bulk operations.
- **Analyzed**: 2026-06-21T20:03:25.904Z
- **Commit**: a4090a85a5f95825c49f4f1061b6dcc738796502
- **Nodes**: 372 | **Edges**: 654

## Node Inventory

- function: 249
- class: 56
- file: 54
- document: 8
- config: 3
- service: 1
- pipeline: 1

## Key Components Overview

- **app.py** (`tube-manager/app.py`) — Source file app.py — part of the motus.leap project.
- **ConnectionManager** (`tube-manager/app.py`) — Class ConnectionManager defining data structures and behavior.
- **ActionIn** (`tube-manager/app.py`) — Class ActionIn defining data structures and behavior.
- **MappingIn** (`tube-manager/app.py`) — Class MappingIn defining data structures and behavior.
- **MappingsIn** (`tube-manager/app.py`) — Class MappingsIn defining data structures and behavior.
- **ConfigUpdateIn** (`tube-manager/app.py`) — Class ConfigUpdateIn defining data structures and behavior.
- **WatchLaterMoveIn** (`tube-manager/app.py`) — Class WatchLaterMoveIn defining data structures and behavior.
- **SettingsIn** (`tube-manager/app.py`) — Class SettingsIn defining data structures and behavior.
- **AIClassifyIn** (`tube-manager/app.py`) — Class AIClassifyIn defining data structures and behavior.
- **RecordMoveIn** (`tube-manager/app.py`) — Class RecordMoveIn defining data structures and behavior.
- **auth.py** (`tube-manager/api/auth.py`) — Source file auth.py — part of the motus.leap project.
- **__init__.py** (`tube-manager/core/__init__.py`) — Source file __init__.py — part of the motus.leap project.
- **http_client.py** (`tube-manager/core/http_client.py`) — Source file http_client.py — part of the motus.leap project.
- **limiter.py** (`tube-manager/core/limiter.py`) — Source file limiter.py — part of the motus.leap project.
- **logger.py** (`tube-manager/core/logger.py`) — Source file logger.py — part of the motus.leap project.
- **__init__.py** (`tube-manager/models/__init__.py`) — Source file __init__.py — part of the motus.leap project.
- **task.py** (`tube-manager/models/task.py`) — Source file task.py — part of the motus.leap project.
- **UserCreate** (`tube-manager/api/auth.py`) — Class UserCreate defining data structures and behavior.
- **UserLogin** (`tube-manager/api/auth.py`) — Class UserLogin defining data structures and behavior.
- **UserUpdate** (`tube-manager/api/auth.py`) — Class UserUpdate defining data structures and behavior.
- **UserResponse** (`tube-manager/api/auth.py`) — Class UserResponse defining data structures and behavior.
- **TokenResponse** (`tube-manager/api/auth.py`) — Class TokenResponse defining data structures and behavior.
- **PasswordResetRequest** (`tube-manager/api/auth.py`) — Class PasswordResetRequest defining data structures and behavior.
- **PasswordResetConfirm** (`tube-manager/api/auth.py`) — Class PasswordResetConfirm defining data structures and behavior.

## Notable Relationships

- tube-manager/app.py → tube-manager/app.py:require_auth [relates to] x2
- tube-manager/app.py → tube-manager/app.py:no_cache_file_response [relates to] x2
- tube-manager/app.py → tube-manager/app.py:lifespan [relates to] x2
- tube-manager/app.py → tube-manager/app.py:add_security_headers [relates to] x2
- tube-manager/app.py → tube-manager/app.py:fetch_all_youtube_data [relates to] x2
- tube-manager/app.py → tube-manager/app.py:api_playlist_names [relates to] x2
- tube-manager/app.py → tube-manager/app.py:get_watch_later [relates to] x2
- tube-manager/app.py → tube-manager/app.py:move_watch_later_videos [relates to] x2
- tube-manager/app.py → tube-manager/app.py:get_youtube_videos [relates to] x2
- tube-manager/app.py → tube-manager/app.py:scan_duplicates_endpoint [relates to] x2
- tube-manager/app.py → tube-manager/app.py:scan_misplaced_endpoint [relates to] x2
- tube-manager/app.py → tube-manager/app.py:stats [relates to] x2
- tube-manager/app.py → tube-manager/app.py:rename_playlist_endpoint [relates to] x2
- tube-manager/app.py → tube-manager/app.py:delete_playlist_endpoint [relates to] x2
- tube-manager/app.py → tube-manager/app.py:duplicate_playlist_endpoint [relates to] x2
- tube-manager/app.py → tube-manager/app.py:delete_playlist_item_endpoint [relates to] x2
- tube-manager/app.py → tube-manager/app.py:api_maintenance [relates to] x2
- tube-manager/app.py → tube-manager/app.py:_normalize_mappings [relates to] x2
- tube-manager/app.py → tube-manager/app.py:_extract_mapping_items [relates to] x2
- tube-manager/app.py → tube-manager/app.py:api_mappings [relates to] x2
- tube-manager/app.py → tube-manager/app.py:youtube_auth [relates to] x2
- tube-manager/app.py → tube-manager/app.py:youtube_callback [relates to] x2
- tube-manager/app.py → tube-manager/app.py:youtube_disconnect [relates to] x2
- tube-manager/app.py → tube-manager/app.py:get_settings [relates to] x2
- tube-manager/app.py → tube-manager/app.py:save_settings [relates to] x2

## Recommendations
- Review the code review findings from `/tmp/motus.leap` prior integration work.
- Prioritize critical issues first: import/dependency ordering, OAuth secret exposure, and undefined identifiers in background workers.
- Consider using `/understand-knowledge` if docs/wikis need a navigable knowledge graph alongside the codebase graph.
