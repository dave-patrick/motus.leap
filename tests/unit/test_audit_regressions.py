"""Behavior regressions from the performance and UX audit; no external services."""
from unittest.mock import AsyncMock
import uuid
import pytest
from fastapi.testclient import TestClient
from api import auth
import app as app_module
from models.config import TubeManagerConfig
from services.youtube_service import YouTubeService


@pytest.fixture
def authenticated(monkeypatch, tmp_path):
    user = {"id": "audit", "username": "audit", "role": "admin", "is_active": True}
    monkeypatch.setattr(auth, "_cached_users_db", {"audit": user})
    monkeypatch.setattr(auth, "_revoked_tokens", set())
    monkeypatch.setattr(auth, "_REVOKED_TOKENS_FILE", tmp_path / 'revoked.json')
    monkeypatch.setattr(auth, "_save_sessions", AsyncMock())
    token = auth.create_access_token({"sub": "audit", "jti": uuid.uuid4().hex})
    client = TestClient(app_module.app, base_url='http://localhost:8000')
    client.cookies.set('token', token)
    yield client, token
    client.close()


def test_logout_revokes_copied_bearer(authenticated):
    client, token = authenticated
    assert client.post('/api/auth/logout', headers={'Origin': 'http://localhost:8000'}).status_code == 200
    assert client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'}).status_code == 401


def test_debug_status_requires_admin_and_contains_no_credentials(authenticated, monkeypatch):
    client, _ = authenticated
    payload = client.get('/api/youtube/debug-status').json()
    assert 'access_token' not in payload and 'refresh_token' not in payload and 'config_file' not in payload
    monkeypatch.setitem(auth._cached_users_db['audit'], 'role', 'user')
    assert client.get('/api/youtube/debug-status').status_code == 403
    client.cookies.clear()
    assert client.get('/api/youtube/debug-status').status_code == 401


@pytest.mark.parametrize('path', ['/api/youtube/playlistitems/delete', '/api/maintenance/remove-deleted', '/api/maintenance/move-private', '/api/system/logs/clear'])
def test_mutation_rejects_foreign_origin(authenticated, path):
    client, _ = authenticated
    assert client.post(path, json={}, headers={'Origin': 'https://foreign.example'}).status_code == 403


@pytest.mark.asyncio
async def test_disk_cache_isolated_and_invalidated(tmp_path):
    first = YouTubeService(TubeManagerConfig())
    second = YouTubeService(TubeManagerConfig())
    first._user_data_dir = tmp_path / 'one'
    second._user_data_dir = tmp_path / 'two'
    await first._save_to_disk('playlist_videos_PL1', [{'video_id': 'one'}])
    assert await first._load_from_disk('playlist_videos_PL1') == [{'video_id': 'one'}]
    assert await second._load_from_disk('playlist_videos_PL1') is None
    await first._cache.set('playlist_videos_PL1', [{'video_id': 'one'}])
    await first._cache_invalidate_playlist('PL1')
    assert await first._load_from_disk('playlist_videos_PL1') is None
    assert await first._cache.get('playlist_videos_PL1') is None


def test_static_js_revalidated_after_deploy():
    client = TestClient(app_module.app)
    response = client.get('/static/auth-check.js')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'public, max-age=0, must-revalidate'
    assert 'etag' in response.headers
    cached = client.get('/static/auth-check.js', headers={'If-None-Match': response.headers['etag']})
    assert cached.status_code == 304


def test_websocket_accepts_cookie_session_and_answers_ping(authenticated):
    client, _ = authenticated
    with client.websocket_connect('/ws/terminal', headers={'Origin': 'http://localhost:8000'}) as ws:
        assert ws.receive_json()['type'] == 'log'
        ws.send_json({'type': 'ping'})
        assert ws.receive_json() == {'type': 'pong'}


def test_log_tail_reads_recent_lines_with_bounded_bytes(tmp_path):
    from core.logger import read_log_tail
    path = tmp_path / 'server.log'
    path.write_text('old line\n' * 10000 + 'recent one\nrecent two\n')
    assert read_log_tail(path, limit=2, max_bytes=128) == ['recent one', 'recent two']


@pytest.mark.asyncio
async def test_worker_errors_persist_without_live_clients(caplog):
    import logging
    from services.background_worker import BackgroundWorker
    worker = BackgroundWorker.__new__(BackgroundWorker)
    worker.manager = None
    with caplog.at_level(logging.INFO, logger='services.background_worker'):
        await worker._safe_broadcast({'type': 'log', 'message': '[ERROR] Test failure'})
    assert any(record.levelname == 'ERROR' and record.message == '[ERROR] Test failure' for record in caplog.records)
