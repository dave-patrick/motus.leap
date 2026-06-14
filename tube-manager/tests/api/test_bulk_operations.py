"""Tests for bulk operations implementation."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from api.bulk_operations_impl import BulkOperationsService
from models.config import TubeManagerConfig, YouTubeOAuthConfig
from core.config_manager import ConfigManager


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    oauth = YouTubeOAuthConfig(
        client_id="test_client_id",
        client_secret="test_secret",
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        token_expiry=None
    )

    config = Mock(spec=TubeManagerConfig)
    config.oauth = oauth
    config.youtube_api_key = None
    config.token_expiry = None

    return config


@pytest.fixture
def mock_config_manager():
    """Create mock config manager."""
    manager = Mock()
    manager.config = Mock()
    manager.config.channel_mappings = {}
    manager.save = Mock()
    return manager


@pytest.fixture
def bulk_service(mock_config, mock_config_manager):
    """Create bulk operations service."""
    return BulkOperationsService(mock_config, mock_config_manager)


class TestBulkOperationsService:
    """Test bulk operations service."""

    @pytest.mark.asyncio
    async def test_get_client_with_oauth(self, bulk_service):
        """Test getting client with OAuth."""
        client = bulk_service._get_client()
        assert client is not None

    def test_get_client_without_oauth(self, mock_config, mock_config_manager):
        """Test getting client without OAuth fails."""
        mock_config.oauth.access_token = None
        service = BulkOperationsService(mock_config, mock_config_manager)
        client = service._get_client()
        assert client is None

    @pytest.mark.asyncio
    async def test_export_mappings(self, bulk_service, mock_config_manager):
        """Test exporting mappings."""
        mock_config_manager.config.channel_mappings = {
            "Channel1": "playlist1",
            "Channel2": "playlist2"
        }

        result = await bulk_service.export_mappings()

        assert result == {
            "Channel1": "playlist1",
            "Channel2": "playlist2"
        }

    @pytest.mark.asyncio
    async def test_import_mappings_merge(self, bulk_service, mock_config_manager):
        """Test importing mappings in merge mode."""
        mock_config_manager.config.channel_mappings = {
            "Existing": "existing_playlist"
        }

        items = [
            {"channel": "New1", "playlist": "new_playlist1"},
            {"channel": "New2", "playlist": "new_playlist2"}
        ]

        count = await bulk_service.import_mappings(items, {"mode": "merge"})

        assert count == 2
        assert mock_config_manager.save.called

    @pytest.mark.asyncio
    async def test_import_mappings_replace(self, bulk_service, mock_config_manager):
        """Test importing mappings in replace mode."""
        mock_config_manager.config.channel_mappings = {
            "Existing": "existing_playlist"
        }

        items = [
            {"channel": "New1", "playlist": "new_playlist1"}
        ]

        count = await bulk_service.import_mappings(items, {"mode": "replace"})

        assert count == 1
        assert mock_config_manager.save.called

    @pytest.mark.asyncio
    async def test_import_mappings_invalid_mode(self, bulk_service):
        """Test importing mappings with invalid mode raises error."""
        items = [{"channel": "Test", "playlist": "playlist1"}]

        with pytest.raises(ValueError, match="Invalid import mode"):
            await bulk_service.import_mappings(items, {"mode": "invalid"})

    @pytest.mark.asyncio
    @patch('api.bulk_operations_impl.YouTubeClient')
    async def test_move_video_success(self, mock_youtube_client_class, bulk_service):
        """Test moving video successfully."""
        # Mock the YouTube client
        mock_client = Mock()
        mock_api = Mock()

        # Mock videos().list() response
        mock_api.videos().list().execute.return_value = {
            "items": [{
                "snippet": {
                    "title": "Test Video",
                    "description": "Test Description",
                    "categoryId": "1"
                }
            }]
        }

        # Mock playlistItems().insert() response
        mock_api.playlistItems().insert().execute.return_value = {
            "id": "playlist_item_id"
        }

        # Mock playlistItems().list() for source removal
        mock_api.playlistItems().list().execute.return_value = {
            "items": [{"id": "source_item_id"}]
        }

        # Mock playlistItems().delete()
        mock_api.playlistItems().delete().execute.return_value = None

        mock_client._get_client.return_value = mock_api
        mock_youtube_client_class.return_value = mock_client

        result = await bulk_service.move_video(
            "video123",
            "target_playlist",
            "source_playlist"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_move_video_no_client(self, bulk_service):
        """Test moving video without client fails."""
        bulk_service.config.oauth.access_token = None
        result = await bulk_service.move_video("video123", "target")
        assert result is False

    @pytest.mark.asyncio
    @patch('api.bulk_operations_impl.YouTubeClient')
    async def test_delete_video_success(self, mock_youtube_client_class, bulk_service):
        """Test deleting video successfully."""
        mock_client = Mock()
        mock_api = Mock()

        # Mock playlistItems().list() response
        mock_api.playlistItems().list().execute.return_value = {
            "items": [{"id": "playlist_item_id"}]
        }

        # Mock playlistItems().delete()
        mock_api.playlistItems().delete().execute.return_value = None

        mock_client._get_client.return_value = mock_api
        mock_youtube_client_class.return_value = mock_client

        result = await bulk_service.delete_video("video123", "playlist123")

        assert result is True

    @pytest.mark.asyncio
    @patch('api.bulk_operations_impl.YouTubeClient')
    async def test_tag_video_add(self, mock_youtube_client_class, bulk_service):
        """Test adding tags to video."""
        mock_client = Mock()
        mock_api = Mock()

        # Mock videos().list() response
        mock_api.videos().list().execute.return_value = {
            "items": [{
                "snippet": {
                    "title": "Test Video",
                    "description": "Test Description",
                    "categoryId": "1",
                    "tags": ["existing_tag"]
                }
            }]
        }

        # Mock videos().update() response
        mock_api.videos().update().execute.return_value = {
            "id": "video123"
        }

        mock_client._get_client.return_value = mock_api
        mock_youtube_client_class.return_value = mock_client

        result = await bulk_service.tag_video(
            "video123",
            ["new_tag", "another_tag"],
            "add"
        )

        assert result is True

    @pytest.mark.asyncio
    @patch('api.bulk_operations_impl.YouTubeClient')
    async def test_tag_video_remove(self, mock_youtube_client_class, bulk_service):
        """Test removing tags from video."""
        mock_client = Mock()
        mock_api = Mock()

        # Mock videos().list() response
        mock_api.videos().list().execute.return_value = {
            "items": [{
                "snippet": {
                    "title": "Test Video",
                    "description": "Test Description",
                    "categoryId": "1",
                    "tags": ["tag1", "tag2", "tag3"]
                }
            }]
        }

        # Mock videos().update() response
        mock_api.videos().update().execute.return_value = {
            "id": "video123"
        }

        mock_client._get_client.return_value = mock_api
        mock_youtube_client_class.return_value = mock_client

        result = await bulk_service.tag_video(
            "video123",
            ["tag2"],
            "remove"
        )

        assert result is True

    @pytest.mark.asyncio
    @patch('api.bulk_operations_impl.YouTubeClient')
    async def test_export_playlists(self, mock_youtube_client_class, bulk_service):
        """Test exporting playlists."""
        mock_client = Mock()
        mock_client.list_mine_playlists.return_value = {
            "items": [{
                "id": "pl123",
                "snippet": {
                    "title": "Test Playlist",
                    "description": "Description",
                    "publishedAt": "2026-06-14T00:00:00Z",
                    "privacyStatus": "public"
                },
                "contentDetails": {
                    "itemCount": 10
                }
            }]
        }

        mock_youtube_client_class.return_value = mock_client

        result = await bulk_service.export_playlists()

        assert len(result) == 1
        assert result[0]["id"] == "pl123"
        assert result[0]["title"] == "Test Playlist"
        assert result[0]["item_count"] == 10

    @pytest.mark.asyncio
    @patch('api.bulk_operations_impl.YouTubeClient')
    async def test_export_subscriptions(self, mock_youtube_client_class, bulk_service):
        """Test exporting subscriptions."""
        mock_client = Mock()
        mock_client.list_mine_subscriptions.return_value = {
            "items": [{
                "snippet": {
                    "title": "Test Channel",
                    "description": "Channel Description",
                    "publishedAt": "2026-06-14T00:00:00Z",
                    "resourceId": {
                        "channelId": "ch123"
                    },
                    "thumbnails": {
                        "default": {
                            "url": "https://example.com/thumb.jpg"
                        }
                    }
                }
            }]
        }

        mock_youtube_client_class.return_value = mock_client

        result = await bulk_service.export_subscriptions()

        assert len(result) == 1
        assert result[0]["id"] == "ch123"
        assert result[0]["title"] == "Test Channel"