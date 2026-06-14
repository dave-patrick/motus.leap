"""Bulk operations implementation using YouTube Data API v3."""

import logging
import base64
import csv
import json
import io
from typing import List, Dict, Any, Optional
from datetime import datetime

from services.youtube_client import YouTubeClient
from models.config import TubeManagerConfig
from core.config_manager import ConfigManager

log = logging.getLogger(__name__)


class BulkOperationsService:
    """Service for handling bulk operations on YouTube."""

    def __init__(self, config: TubeManagerConfig, config_manager: ConfigManager):
        """Initialize bulk operations service.

        Args:
            config: Application configuration
            config_manager: Configuration manager for persistence
        """
        self.config = config
        self.config_manager = config_manager

    def _get_client(self) -> Optional[YouTubeClient]:
        """Get authenticated YouTube client for write operations.

        Returns:
            YouTubeClient instance or None if not authenticated
        """
        if not self.config.oauth.access_token:
            log.error("OAuth token required for bulk operations")
            return None

        return YouTubeClient(
            api_key=None,  # Use OAuth for write operations
            oauth_access_token=self.config.oauth.access_token,
            oauth_refresh_token=self.config.oauth.refresh_token,
            oauth_client_id=self.config.oauth.client_id,
            oauth_client_secret=self.config.oauth.client_secret.get_secret_value() if self.config.oauth.client_secret else None,
            token_expiry=self.config.token_expiry,
        )

    async def move_video(
        self,
        video_id: str,
        target_playlist_id: str,
        source_playlist_id: Optional[str] = None
    ) -> bool:
        """Move a video to a target playlist.

        Args:
            video_id: YouTube video ID
            target_playlist_id: Destination playlist ID
            source_playlist_id: Source playlist ID (if provided, remove from source)

        Returns:
            True if successful, False otherwise
        """
        client = self._get_client()
        if not client:
            log.error("Failed to get YouTube client for move operation")
            return False

        try:
            # Get the API client
            youtube = client._get_client(require_oauth=True)
            if not youtube:
                log.error("Failed to get authenticated YouTube API client")
                return False

            # Get the video details to preserve position
            try:
                video_response = youtube.videos().list(
                    part="snippet",
                    id=video_id
                ).execute()

                if not video_response.get("items"):
                    log.warning(f"Video {video_id} not found")
                    return False

                video_snippet = video_response["items"][0]["snippet"]
            except Exception as e:
                log.error(f"Failed to get video details for {video_id}: {e}")
                return False

            # Add video to target playlist
            try:
                insert_response = youtube.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": target_playlist_id,
                            "resourceId": {
                                "kind": "youtube#video",
                                "videoId": video_id
                            }
                        }
                    }
                ).execute()
                log.info(f"Added video {video_id} to playlist {target_playlist_id}")
            except Exception as e:
                log.error(f"Failed to add video {video_id} to playlist {target_playlist_id}: {e}")
                return False

            # If source playlist is provided, remove from source
            if source_playlist_id and source_playlist_id != target_playlist_id:
                try:
                    # Find the playlist item ID for this video in the source playlist
                    playlist_items = youtube.playlistItems().list(
                        part="id",
                        playlistId=source_playlist_id,
                        videoId=video_id
                    ).execute()

                    for item in playlist_items.get("items", []):
                        # Delete the playlist item
                        youtube.playlistItems().delete(id=item["id"]).execute()
                        log.info(f"Removed video {video_id} from playlist {source_playlist_id}")
                        break
                except Exception as e:
                    log.warning(f"Failed to remove video {video_id} from source playlist: {e}")
                    # Don't fail the entire operation if removal fails

            return True

        except Exception as e:
            log.error(f"Error moving video {video_id}: {e}")
            return False

    async def delete_video(
        self,
        video_id: str,
        playlist_id: str
    ) -> bool:
        """Delete a video from a playlist (not the video itself).

        Args:
            video_id: YouTube video ID
            playlist_id: Playlist ID to remove from

        Returns:
            True if successful, False otherwise
        """
        client = self._get_client()
        if not client:
            log.error("Failed to get YouTube client for delete operation")
            return False

        try:
            # Get the API client
            youtube = client._get_client(require_oauth=True)
            if not youtube:
                log.error("Failed to get authenticated YouTube API client")
                return False

            # Find the playlist item ID for this video
            playlist_items = youtube.playlistItems().list(
                part="id",
                playlistId=playlist_id,
                videoId=video_id
            ).execute()

            for item in playlist_items.get("items", []):
                # Delete the playlist item
                youtube.playlistItems().delete(id=item["id"]).execute()
                log.info(f"Removed video {video_id} from playlist {playlist_id}")
                return True

            log.warning(f"Video {video_id} not found in playlist {playlist_id}")
            return False

        except Exception as e:
            log.error(f"Error deleting video {video_id} from playlist: {e}")
            return False

    async def tag_video(
        self,
        video_id: str,
        tags: List[str],
        action: str = "add"
    ) -> bool:
        """Add or remove tags from a video's metadata.

        Note: This updates video metadata, which requires owner permissions.

        Args:
            video_id: YouTube video ID
            tags: List of tags to add/remove
            action: "add" or "remove"

        Returns:
            True if successful, False otherwise
        """
        client = self._get_client()
        if not client:
            log.error("Failed to get YouTube client for tag operation")
            return False

        try:
            # Get the API client
            youtube = client._get_client(require_oauth=True)
            if not youtube:
                log.error("Failed to get authenticated YouTube API client")
                return False

            # Get current video details
            video_response = youtube.videos().list(
                part="snippet",
                id=video_id
            ).execute()

            if not video_response.get("items"):
                log.warning(f"Video {video_id} not found")
                return False

            video_snippet = video_response["items"][0]["snippet"]
            current_tags = video_snippet.get("tags", [])

            # Update tags
            if action == "add":
                new_tags = list(set(current_tags + tags))
            else:  # remove
                new_tags = [t for t in current_tags if t not in tags]

            # Update video
            update_response = youtube.videos().update(
                part="snippet",
                body={
                    "id": video_id,
                    "snippet": {
                        "title": video_snippet["title"],
                        "description": video_snippet["description"],
                        "tags": new_tags,
                        "categoryId": video_snippet["categoryId"]
                    }
                }
            ).execute()

            log.info(f"Updated tags for video {video_id}: {action} {tags}")
            return True

        except Exception as e:
            log.error(f"Error tagging video {video_id}: {e}")
            return False

    async def import_mappings(
        self,
        items: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None
    ) -> int:
        """Import channel mappings.

        Args:
            items: List of channel mapping items
            options: Import options (merge or replace)

        Returns:
            Number of successfully imported mappings
        """
        try:
            config = self.config_manager.config
            mode = options.get("mode", "merge") if options else "merge"

            if mode == "replace":
                config.channel_mappings = {}
            elif mode != "merge":
                raise ValueError(f"Invalid import mode: {mode}")

            # Parse mappings
            for item in items:
                channel = item.get("channel") or item.get("Channel")
                playlist = item.get("playlist") or item.get("Playlist")

                if channel and playlist:
                    config.channel_mappings[channel] = playlist

            # Save configuration
            self.config_manager.save(config)
            log.info(f"Imported {len(items)} channel mappings")
            return len(items)

        except Exception as e:
            log.error(f"Error importing mappings: {e}")
            return 0

    async def export_playlists(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Export playlists data.

        Args:
            filters: Optional filters for export

        Returns:
            List of playlist data
        """
        try:
            client = self._get_client()
            if not client:
                return []

            # Get all playlists
            playlists_response = client.list_mine_playlists(max_results=50)

            playlists_data = []
            for item in playlists_response.get("items", []):
                playlist_id = item["id"]
                snippet = item["snippet"]

                # Get playlist item count
                try:
                    playlist_details = client.get_playlist(playlist_id)
                    item_count = playlist_details.get("contentDetails", {}).get("itemCount", 0)
                except:
                    item_count = 0

                playlists_data.append({
                    "id": playlist_id,
                    "title": snippet["title"],
                    "description": snippet.get("description", ""),
                    "item_count": item_count,
                    "created_at": snippet.get("publishedAt"),
                    "privacy": snippet.get("privacyStatus", "public")
                })

            return playlists_data

        except Exception as e:
            log.error(f"Error exporting playlists: {e}")
            return []

    async def export_subscriptions(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Export subscriptions data.

        Args:
            filters: Optional filters for export

        Returns:
            List of subscription data
        """
        try:
            client = self._get_client()
            if not client:
                return []

            # Get all subscriptions
            subs_response = client.list_mine_subscriptions(max_results=50)

            subs_data = []
            for item in subs_response.get("items", []):
                snippet = item["snippet"]

                subs_data.append({
                    "id": snippet["resourceId"]["channelId"],
                    "title": snippet["title"],
                    "description": snippet.get("description", ""),
                    "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url"),
                    "subscribed_at": snippet.get("publishedAt")
                })

            return subs_data

        except Exception as e:
            log.error(f"Error exporting subscriptions: {e}")
            return []

    async def export_mappings(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """Export channel mappings.

        Args:
            filters: Optional filters for export

        Returns:
            Dictionary of channel mappings
        """
        try:
            config = self.config_manager.config
            return dict(config.channel_mappings)

        except Exception as e:
            log.error(f"Error exporting mappings: {e}")
            return {}