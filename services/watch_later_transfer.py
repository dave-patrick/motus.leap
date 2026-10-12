"""Move one Watch Later item without removing an unsaved source copy."""
import time
from urllib.parse import urlparse, parse_qs


def read_current_watch_later(driver):
    driver.get("https://www.youtube.com/playlist?list=WL")
    videos, stable = {}, 0
    for attempt in range(200):
        rows = driver.execute_script("""return Array.from(document.querySelectorAll('ytd-playlist-video-renderer, ytd-playlist-panel-video-renderer, yt-lockup-view-model')).map(el => {
          const a=el.querySelector('a[href*="watch?v="]');
          return a ? {url:a.href,title:(el.querySelector('#video-title,h3')?.textContent || a.textContent || '').trim()} : null;
        }).filter(Boolean);""") or []
        before = len(videos)
        for row in rows:
            video_id = parse_qs(urlparse(row.get("url", "")).query).get("v", [None])[0]
            if video_id:
                videos[video_id] = {**row, "video_id": video_id}
        stable = stable + 1 if len(videos) == before else 0
        if stable >= 6 and attempt >= 10:
            if not videos:
                raise RuntimeError("No videos were read. Watch Later may be empty, or your YouTube session needs reconnecting.")
            expected = driver.execute_script("""const header=document.querySelector('ytd-playlist-header-renderer,ytd-playlist-sidebar-primary-info-renderer');
              const match=header?.innerText.match(/([\\d,]+)\\s+videos?/i); return match ? Number(match[1].replaceAll(',','')) : null;""")
            if expected is not None and int(expected) > len(videos):
                raise RuntimeError("Watch Later did not fully load. No videos were moved; try again.")
            return list(videos.values())
        driver.execute_script("window.scrollTo(0,document.documentElement.scrollHeight);")
        time.sleep(1)
    raise RuntimeError("Watch Later is still loading. No videos were moved; try again.")


def transfer_item(client, driver, target_id, video):
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
