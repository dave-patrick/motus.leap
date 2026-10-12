"""Move Watch Later items over YouTube's web API, without a browser.

Reading Watch Later and removing a video from it both run on InnerTube in
services/youtube_innertube.py, so a 512 MiB instance never has to launch
Chromium. The optional driver arguments are kept for callers that still hold a
local browser session.
"""


def read_current_watch_later(driver=None):
    """Return every Watch Later video, newest first, as YouTube orders them."""
    from services.youtube_innertube import (
        InnerTubeError,
        WatchLaterSessionError,
        list_watch_later,
    )

    try:
        return list_watch_later()
    except WatchLaterSessionError:
        # A browser cannot help: it would be signed out in exactly the same way.
        raise
    except InnerTubeError:
        if driver is None:
            raise
    from core.actions import list_videos_in_playlist

    return list_videos_in_playlist("https://www.youtube.com/playlist?list=WL", driver=driver)


def transfer_item(client, driver=None, target_id=None, video=None):
    """Save one Watch Later entry into target_id, then drop it from Watch Later."""
    from core.actions import remove_video_from_playlist

    video_id = video.get("video_id") or video.get("id")
    if not video_id:
        raise ValueError("This Watch Later entry has no video ID.")
    youtube = client._get_client(require_oauth=True)
    existing = youtube.playlistItems().list(
        part="id", playlistId=target_id, videoId=video_id, maxResults=1
    ).execute()
    if not existing.get("items"):
        saved = client.add_video_to_playlist(target_id, video_id)
        if not isinstance(saved, dict) or not saved.get("id"):
            raise RuntimeError("YouTube did not confirm the addition to 1~Sort. Watch Later was kept unchanged.")
    # Only remove after the target is known to contain this video.
    if not remove_video_from_playlist(
        f"https://www.youtube.com/watch?v={video_id}", "Watch Later", driver=driver
    ):
        raise RuntimeError("Saved in 1~Sort, but removal from Watch Later was not confirmed.")
    return video_id
