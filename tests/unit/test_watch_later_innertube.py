"""Watch Later over InnerTube, with no browser process involved.

These tests pin the behaviour the Watch Later rework bought: the cookie store
that already fed Playwright now drives plain HTTP calls, and a signed-out
session is reported as a signed-out session instead of being retried in
headless Chromium (which fails identically, hundreds of megabytes later).
"""

import hashlib
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from core import actions
from services import watch_later_service, watch_later_transfer, youtube_innertube
from services.youtube_innertube import (
    InnerTubeError,
    WatchLaterSessionError,
    list_watch_later,
    remove_from_watch_later,
)

HOME_HTML = (
    "<script>"
    '{"INNERTUBE_API_KEY":"test-key","INNERTUBE_CLIENT_VERSION":"2.2024.01.01.00"}'
    "</script>"
)
SAPISID = "sapisid-value"
BROWSE_URL = "https://www.youtube.com/youtubei/v1/browse"


def _response(payload=None, *, text="", status_code=200, url=BROWSE_URL):
    request = httpx.Request("POST", url)
    if payload is None:
        return httpx.Response(status_code, text=text, request=request)
    return httpx.Response(status_code, json=payload, request=request)


def _logged_in(value):
    return {
        "responseContext": {
            "serviceTrackingParams": [{"params": [{"key": "logged_in", "value": value}]}]
        }
    }


def _video_entry(video_id):
    return {
        "playlistVideoRenderer": {
            "videoId": video_id,
            "title": {"simpleText": f"Title {video_id}"},
            "shortBylineText": {"runs": [{"text": f"Channel {video_id}"}]},
        }
    }


def _video_page(video_ids, *, continuation=None, logged_in="1"):
    items = [_video_entry(video_id) for video_id in video_ids]
    if continuation:
        items.append(
            {
                "continuationItemRenderer": {
                    "continuationEndpoint": {
                        "continuationCommand": {"token": continuation}
                    }
                }
            }
        )
    payload = {
        "contents": {"twoColumnBrowseResultsRenderer": {"tabs": [{"items": items}]}},
        **_logged_in(logged_in),
    }
    return _response(payload)


class FakeClient:
    """Stands in for httpx.Client: records calls, replays canned responses."""

    def __init__(self, *, home=HOME_HTML, posts=None):
        self._home = home
        self._posts = list(posts or [])
        self.posts = []
        self.gets = []

    def get(self, url, headers=None):
        self.gets.append({"url": url, "headers": headers or {}})
        return _response(text=self._home)

    def post(self, url, headers=None, json=None):
        self.posts.append({"url": url, "headers": headers or {}, "json": json})
        if not self._posts:
            raise AssertionError(f"unexpected InnerTube POST to {url}")
        return self._posts.pop(0)

    def close(self):
        pass


@pytest.fixture(autouse=True)
def cookie_store(tmp_path, monkeypatch):
    """Point the InnerTube module at a temporary signed-in cookie store."""
    path = tmp_path / "youtube_cookies.json"
    path.write_text(
        json.dumps(
            [
                {"name": "SAPISID", "value": SAPISID, "domain": ".youtube.com"},
                {"name": "SID", "value": "sid-value", "domain": ".youtube.com"},
                {"name": "unrelated", "value": "noise", "domain": ".example.com"},
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("core.actions.get_youtube_cookies_path", lambda: str(path))
    youtube_innertube.reset_cache()
    yield path
    youtube_innertube.reset_cache()


@pytest.mark.unit
def test_list_watch_later_reads_renderers():
    client = FakeClient(posts=[_video_page(["abcdefghijk", "lmnopqrstuv"])])
    videos = list_watch_later(client=client)
    assert [video["video_id"] for video in videos] == ["abcdefghijk", "lmnopqrstuv"]
    assert videos[0]["id"] == "abcdefghijk"
    assert videos[0]["title"] == "Title abcdefghijk"
    assert videos[0]["channel"] == "Channel abcdefghijk"
    assert videos[0]["url"] == "https://www.youtube.com/watch?v=abcdefghijk"
    assert client.posts[0]["json"]["browseId"] == "VLWL"


@pytest.mark.unit
def test_list_watch_later_follows_continuation_pages():
    client = FakeClient(
        posts=[
            _video_page(["abcdefghijk"], continuation="page-two-token"),
            _video_page(["lmnopqrstuv"]),
        ]
    )
    videos = list_watch_later(client=client)
    assert [video["video_id"] for video in videos] == ["abcdefghijk", "lmnopqrstuv"]
    assert len(client.posts) == 2
    assert client.posts[1]["json"]["continuation"] == "page-two-token"


@pytest.mark.unit
def test_list_watch_later_skips_non_video_lockups():
    client = FakeClient(
        posts=[
            _response(
                {
                    "contents": {
                        "items": [
                            {"lockupViewModel": {"contentId": "PLplaylistid"}},
                            {
                                "lockupViewModel": {
                                    "contentId": "lmnopqrstuv",
                                    "metadata": {
                                        "lockupMetadataViewModel": {
                                            "title": {"content": "Lockup title"}
                                        }
                                    },
                                }
                            },
                        ]
                    },
                    **_logged_in("1"),
                }
            )
        ]
    )
    videos = list_watch_later(client=client)
    assert [video["video_id"] for video in videos] == ["lmnopqrstuv"]
    assert videos[0]["title"] == "Lockup title"


@pytest.mark.unit
def test_requests_carry_the_sapisidhash_signature():
    client = FakeClient(posts=[_video_page(["abcdefghijk"])])
    list_watch_later(client=client)
    headers = client.posts[0]["headers"]
    scheme, _, signature = headers["Authorization"].partition(" ")
    assert scheme == "SAPISIDHASH"
    timestamp, _, digest = signature.partition("_")
    expected = hashlib.sha1(
        f"{timestamp} {SAPISID} https://www.youtube.com".encode()
    ).hexdigest()
    assert digest == expected
    assert f"SAPISID={SAPISID}" in headers["Cookie"]
    assert "unrelated" not in headers["Cookie"]
    assert "key=test-key" in client.posts[0]["url"]


@pytest.mark.unit
def test_signed_out_browse_raises_session_error():
    client = FakeClient(
        posts=[
            _response(
                {
                    **_logged_in("0"),
                    "alerts": [
                        {"alertRenderer": {"text": {"simpleText": "The playlist does not exist."}}}
                    ],
                }
            )
        ]
    )
    with pytest.raises(WatchLaterSessionError, match="no longer signed in"):
        list_watch_later(client=client)


@pytest.mark.unit
def test_missing_cookies_raises_session_error(monkeypatch):
    monkeypatch.setattr("core.actions.get_youtube_cookies_path", lambda: "")
    with pytest.raises(WatchLaterSessionError):
        list_watch_later(client=FakeClient())


@pytest.mark.unit
def test_remove_from_watch_later_requires_youtube_confirmation():
    client = FakeClient(posts=[_response({"status": "STATUS_SUCCEEDED"})])
    assert remove_from_watch_later("abcdefghijk", client=client) is True
    body = client.posts[0]["json"]
    assert body["playlistId"] == "WL"
    assert body["actions"] == [
        {"action": "ACTION_REMOVE_VIDEO_BY_VIDEO_ID", "removedVideoId": "abcdefghijk"}
    ]


@pytest.mark.unit
def test_remove_without_confirmation_raises():
    client = FakeClient(posts=[_response({"status": "STATUS_FAILED"})])
    with pytest.raises(InnerTubeError, match="did not confirm"):
        remove_from_watch_later("abcdefghijk", client=client)


@pytest.mark.unit
def test_remove_signed_out_raises_session_error():
    client = FakeClient(
        posts=[
            _response(
                {
                    **_logged_in("0"),
                    "alerts": [
                        {"alertRenderer": {"text": {"simpleText": "The playlist does not exist."}}}
                    ],
                }
            )
        ]
    )
    with pytest.raises(WatchLaterSessionError):
        remove_from_watch_later("abcdefghijk", client=client)


@pytest.mark.unit
@pytest.mark.parametrize("bad_id", ["", "too-short", None, 12345])
def test_remove_rejects_non_video_ids(bad_id):
    client = FakeClient()
    with pytest.raises(InnerTubeError):
        remove_from_watch_later(bad_id, client=client)
    assert client.posts == []


@pytest.mark.unit
def test_watch_later_read_never_launches_a_browser(monkeypatch):
    browser = MagicMock()
    monkeypatch.setattr("core.actions.get_browser", browser)
    with patch(
        "services.youtube_innertube.list_watch_later",
        return_value=[{"video_id": "abcdefghijk", "title": "T", "url": "u"}],
    ):
        videos = actions.list_videos_in_playlist("Watch Later")
    assert [video["video_id"] for video in videos] == ["abcdefghijk"]
    browser.assert_not_called()


@pytest.mark.unit
def test_watch_later_removal_never_launches_a_browser(monkeypatch):
    browser = MagicMock()
    monkeypatch.setattr("core.actions.get_browser", browser)
    with patch(
        "services.youtube_innertube.remove_from_watch_later", return_value=True
    ) as remove:
        removed = actions.remove_video_from_playlist(
            "https://www.youtube.com/watch?v=abcdefghijk", "Watch Later"
        )
    assert removed is True
    remove.assert_called_once_with("abcdefghijk")
    browser.assert_not_called()


@pytest.mark.unit
def test_signed_out_read_is_fatal_and_not_retried_in_a_browser(monkeypatch):
    browser = MagicMock()
    monkeypatch.setattr("core.actions.get_browser", browser)
    with patch(
        "services.youtube_innertube.list_watch_later",
        side_effect=WatchLaterSessionError("signed out"),
    ):
        with pytest.raises(WatchLaterSessionError):
            actions.list_videos_in_playlist("Watch Later")
    browser.assert_not_called()


@pytest.mark.unit
def test_read_error_without_a_driver_does_not_open_a_browser(monkeypatch):
    browser = MagicMock()
    monkeypatch.setattr("core.actions.get_browser", browser)
    with patch(
        "services.youtube_innertube.list_watch_later", side_effect=InnerTubeError("boom")
    ):
        with pytest.raises(InnerTubeError):
            actions.list_videos_in_playlist("Watch Later")
    browser.assert_not_called()


@pytest.mark.unit
def test_load_watch_later_videos_uses_innertube_without_a_browser(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("services.watch_later_service.DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("services.watch_later_service.BASE_DIR", str(tmp_path / "base"))
    browser = MagicMock(side_effect=AssertionError("a browser must not be launched"))
    monkeypatch.setattr("core.actions.get_browser", browser)
    with patch(
        "services.youtube_innertube.list_watch_later",
        return_value=[
            {
                "video_id": "abcdefghijk",
                "id": "abcdefghijk",
                "title": "T",
                "url": "https://www.youtube.com/watch?v=abcdefghijk",
            }
        ],
    ):
        videos = watch_later_service.load_watch_later_videos(allow_browser=True)
    assert [video["video_id"] for video in videos] == ["abcdefghijk"]
    browser.assert_not_called()


@pytest.mark.unit
def test_read_current_watch_later_uses_innertube_without_a_driver(monkeypatch):
    browser = MagicMock(side_effect=AssertionError("a browser must not be launched"))
    monkeypatch.setattr("core.actions.get_browser", browser)
    with patch(
        "services.youtube_innertube.list_watch_later",
        return_value=[{"video_id": "abcdefghijk"}],
    ):
        videos = watch_later_transfer.read_current_watch_later()
    assert [video["video_id"] for video in videos] == ["abcdefghijk"]
    browser.assert_not_called()


@pytest.mark.unit
def test_read_current_watch_later_signed_out_does_not_fall_back_to_a_driver():
    driver = MagicMock()
    with patch(
        "services.youtube_innertube.list_watch_later",
        side_effect=WatchLaterSessionError("signed out"),
    ), patch("core.actions.list_videos_in_playlist") as browser_read:
        with pytest.raises(WatchLaterSessionError):
            watch_later_transfer.read_current_watch_later(driver)
    browser_read.assert_not_called()