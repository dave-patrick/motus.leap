"""
Pytest configuration and fixtures for Tube Manager test suite.
"""

import asyncio
import json
import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Import app and components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app, config_manager, youtube_service, manager, task_queue
from core.config_manager import ConfigManager
from models.config import TubeManagerConfig
from services.youtube_service import YouTubeService


# =============================================================================
# Pytest Configuration
# =============================================================================

pytest_plugins = ("pytest_asyncio",)


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "security: mark test as a security test"
    )
    config.addinivalue_line(
        "markers", "load: mark test as a load test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (skip on CI)"
    )


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def test_config():
    """Create test configuration."""
    return TubeManagerConfig(
        youtube_api_key="test_api_key",
        oauth=Mock(
            client_id="test_client_id.apps.googleusercontent.com",
            client_secret=Mock(get_secret_value=Mock(return_value="test_secret")),
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            token_expiry=3600
        ),
        channel_mappings={
            "channel1": "playlist1",
            "channel2": "playlist2"
        },
        rules="test rules\nmore rules"
    )


@pytest.fixture
def mock_youtube_service():
    """Create mock YouTube service."""
    mock_service = Mock(spec=YouTubeService)

    # Mock methods
    mock_service._cache = Mock()
    mock_service._cache.get_stats = Mock(return_value={"hit_rate": "95.5%", "hits": 100, "misses": 5})
    mock_service.fetch_all_data = AsyncMock(return_value={
        "playlists": [{"id": "pl1", "title": "Test Playlist"}],
        "subscriptions": [{"id": "ch1", "title": "Test Channel"}],
        "videos": [{"id": "vid1", "title": "Test Video"}]
    })
    mock_service.get_client = Mock(return_value=Mock())

    return mock_service


@pytest.fixture
def test_client(mock_youtube_service):
    """Create test client with mocked dependencies."""
    # Import app here to avoid module-level initialization
    from app import app as fastapi_app

    # Patch youtube_service globally
    import app
    app.youtube_service = mock_youtube_service

    with TestClient(fastapi_app) as client:
        yield client


@pytest_asyncio.fixture
async def async_test_client(mock_youtube_service):
    """Create async test client."""
    # Import app here to avoid module-level initialization
    from app import app as fastapi_app

    # Patch youtube_service globally
    import app
    app.youtube_service = mock_youtube_service

    async with AsyncClient(app=fastapi_app, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_youtube_api_response():
    """Sample YouTube API response."""
    return {
        "items": [
            {
                "id": "playlist1",
                "snippet": {
                    "title": "Test Playlist 1",
                    "description": "Test description"
                },
                "contentDetails": {
                    "itemCount": 10
                }
            },
            {
                "id": "playlist2",
                "snippet": {
                    "title": "Test Playlist 2",
                    "description": "Test description 2"
                },
                "contentDetails": {
                    "itemCount": 20
                }
            }
        ]
    }


@pytest.fixture
def sample_subscriptions_response():
    """Sample YouTube subscriptions response."""
    return {
        "items": [
            {
                "id": "sub1",
                "snippet": {
                    "title": "Test Channel 1",
                    "description": "Test channel description",
                    "resourceId": {
                        "channelId": "channel1"
                    }
                }
            },
            {
                "id": "sub2",
                "snippet": {
                    "title": "Test Channel 2",
                    "description": "Test channel description 2",
                    "resourceId": {
                        "channelId": "channel2"
                    }
                }
            }
        ]
    }


@pytest.fixture
def sample_video_response():
    """Sample YouTube video response."""
    return {
        "items": [
            {
                "id": "vid1",
                "snippet": {
                    "title": "Test Video 1",
                    "description": "Test video description",
                    "channelTitle": "Test Channel 1"
                },
                "contentDetails": {
                    "duration": "PT10M30S"
                },
                "statistics": {
                    "viewCount": "1000",
                    "likeCount": "100"
                }
            }
        ]
    }


@pytest.fixture
def sample_oauth_tokens():
    """Sample OAuth tokens."""
    return {
        "access_token": "ya29.a0AfH6SMBc",
        "refresh_token": "1//0g",
        "expires_in": 3600,
        "token_type": "Bearer"
    }


@pytest.fixture
def sample_channel_mappings():
    """Sample channel mappings."""
    return {
        "Test Channel 1": "playlist1",
        "Test Channel 2": "playlist2",
        "Test Channel 3": "playlist3"
    }


@pytest.fixture
def sample_task():
    """Sample background task."""
    return {
        "id": "task123",
        "action": "full_cluster_scan",
        "payload": {"force": True},
        "status": "pending",
        "created_at": "2026-06-13T00:00:00Z"
    }


@pytest.fixture
def mock_ws_connection():
    """Mock WebSocket connection."""
    mock_ws = Mock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_text = AsyncMock()
    mock_ws.close = AsyncMock()
    return mock_ws


# =============================================================================
# Helpers
# =============================================================================

def create_mock_youtube_client():
    """Create mock YouTube API client."""
    mock_client = Mock()
    mock_client.list_mine_playlists = Mock(return_value={
        "items": [
            {"id": "pl1", "snippet": {"title": "Playlist 1"}},
            {"id": "pl2", "snippet": {"title": "Playlist 2"}}
        ]
    })
    mock_client.list_mine_subscriptions = Mock(return_value={
        "items": [
            {"id": "sub1", "snippet": {"title": "Channel 1"}},
            {"id": "sub2", "snippet": {"title": "Channel 2"}}
        ]
    })
    mock_client.get_playlist_items = Mock(return_value={
        "items": [
            {"id": "vid1", "snippet": {"title": "Video 1"}},
            {"id": "vid2", "snippet": {"title": "Video 2"}}
        ]
    })
    mock_client.get_video_details = Mock(return_value={
        "items": [
            {
                "id": "vid1",
                "snippet": {"title": "Video 1"},
                "contentDetails": {"duration": "PT10M"},
                "statistics": {"viewCount": "1000"}
            }
        ]
    })
    return mock_client


def assert_response_error(response, status_code, error_message=None):
    """Assert that response is an error."""
    assert response.status_code == status_code
    data = response.json()
    assert "error" in data or "detail" in data
    if error_message:
        assert error_message.lower() in str(data).lower()


def assert_response_success(response, status_code=200):
    """Assert that response is successful."""
    assert response.status_code == status_code
    data = response.json()
    assert "error" not in data


def assert_csp_headers(response):
    """Assert that CSP headers are present and correct."""
    assert "Content-Security-Policy" in response.headers
    csp = response.headers["Content-Security-Policy"]
    assert "nonce-" in csp
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp
    assert "frame-ancestors 'none'" in csp


def assert_security_headers(response):
    """Assert that all security headers are present."""
    assert "Content-Security-Policy" in response.headers
    assert "X-Frame-Options" in response.headers
    assert "X-Content-Type-Options" in response.headers
    assert "X-XSS-Protection" in response.headers
    assert "Referrer-Policy" in response.headers
    assert "Permissions-Policy" in response.headers

    # Check values
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


async def wait_for_queue_empty(timeout=5):
    """Wait for task queue to be empty."""
    import time
    start = time.time()
    while not task_queue.empty() and (time.time() - start) < timeout:
        await asyncio.sleep(0.1)
    assert task_queue.empty(), "Task queue did not empty in time"


# =============================================================================
# Cleanup
# =============================================================================

@pytest.fixture(autouse=True)
def cleanup_tasks():
    """Clean up any background tasks after each test."""
    yield
    # Clear task queue
    while not task_queue.empty():
        task_queue.get_nowait()
    # Clear WebSocket connections
    manager.active_connections.clear()


# =============================================================================
# Skip decorators
# =============================================================================

def skip_if_no_api_key():
    """Skip test if no real API key is available."""
    import os
    return pytest.mark.skipif(
        not os.getenv("YOUTUBE_API_KEY"),
        reason="No YouTube API key available"
    )


def skip_slow():
    """Skip slow tests on CI."""
    return pytest.mark.skipif(
        os.getenv("CI") == "true",
        reason="Test is too slow for CI"
    )


# =============================================================================
# Test data generators
# =============================================================================

def generate_test_playlists(count=5):
    """Generate test playlists."""
    return [
        {
            "id": f"pl{i}",
            "snippet": {
                "title": f"Test Playlist {i}",
                "description": f"Test description {i}"
            },
            "contentDetails": {
                "itemCount": i * 10
            }
        }
        for i in range(1, count + 1)
    ]


def generate_test_videos(count=5):
    """Generate test videos."""
    return [
        {
            "id": f"vid{i}",
            "snippet": {
                "title": f"Test Video {i}",
                "description": f"Test video description {i}",
                "channelTitle": f"Test Channel {i % 3 + 1}"
            },
            "contentDetails": {
                "duration": f"PT{i}0M00S"
            },
            "statistics": {
                "viewCount": str(i * 1000),
                "likeCount": str(i * 100)
            }
        }
        for i in range(1, count + 1)
    ]


def generate_test_channels(count=3):
    """Generate test channels."""
    return [
        {
            "id": f"channel{i}",
            "snippet": {
                "title": f"Test Channel {i}",
                "description": f"Test channel description {i}"
            }
        }
        for i in range(1, count + 1)
    ]


# =============================================================================
# Mock decorators
# =============================================================================

def mock_youtube_api_response(func):
    """Decorator to mock YouTube API responses."""
    def wrapper(*args, **kwargs):
        with patch('services.youtube_service.YouTubeClient') as mock_client_class:
            mock_client = create_mock_youtube_client()
            mock_client_class.return_value = mock_client
            return func(*args, **kwargs)
    return wrapper


def mock_oauth_flow(func):
    """Decorator to mock OAuth flow."""
    def wrapper(*args, **kwargs):
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value.json.return_value = {
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "expires_in": 3600,
                "token_type": "Bearer"
            }
            return func(*args, **kwargs)
    return wrapper