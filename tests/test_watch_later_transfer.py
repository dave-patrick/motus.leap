from unittest.mock import MagicMock, patch
import pytest
from services.watch_later_transfer import transfer_item


def client_with_existing(items):
    client = MagicMock()
    client._get_client.return_value.playlistItems.return_value.list.return_value.execute.return_value = {"items": items}
    client.add_video_to_playlist.return_value = {"id": "new-copy"}
    return client


def test_confirmed_addition_precedes_source_removal():
    client = client_with_existing([])
    order = []
    client.add_video_to_playlist.side_effect = lambda *args: order.append("confirmed-add") or {"id": "copy"}
    with patch("core.actions.remove_video_from_playlist", side_effect=lambda *a, **k: order.append("remove") or True):
        transfer_item(client, object(), "sort", {"video_id": "video"})
    assert order == ["confirmed-add", "remove"]


@pytest.mark.parametrize("response", [None, {}, {"error": "quota"}])
def test_unconfirmed_addition_never_removes_watch_later(response):
    client = client_with_existing([])
    client.add_video_to_playlist.return_value = response
    with patch("core.actions.remove_video_from_playlist") as remove:
        with pytest.raises(RuntimeError):
            transfer_item(client, object(), "sort", {"video_id": "video"})
        remove.assert_not_called()


def test_failed_addition_never_removes_watch_later():
    client = client_with_existing([])
    client.add_video_to_playlist.side_effect = RuntimeError("quota")
    with patch("core.actions.remove_video_from_playlist") as remove:
        with pytest.raises(RuntimeError):
            transfer_item(client, object(), "sort", {"video_id": "video"})
        remove.assert_not_called()


def test_existing_target_copy_is_not_duplicated():
    client = client_with_existing([{"id": "existing-copy"}])
    with patch("core.actions.remove_video_from_playlist", return_value=True) as remove:
        transfer_item(client, object(), "sort", {"video_id": "video"})
        remove.assert_called_once()
    client.add_video_to_playlist.assert_not_called()


def test_failed_removal_is_reported_after_saving_copy():
    client = client_with_existing([])
    with patch("core.actions.remove_video_from_playlist", return_value=False):
        with pytest.raises(RuntimeError, match="Saved in 1~Sort"):
            transfer_item(client, object(), "sort", {"video_id": "video"})
    client.add_video_to_playlist.assert_called_once()
