"""Unit tests for playlist exclusions and AI rule creation (P2)."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from models.config import TubeManagerConfig, AIRule
from services.ai_chat import _tool_create_rule, _tool_apply_rules, run_chat


def test_config_excluded_playlists_defaults_and_roundtrip():
    """Verify excluded_playlists field in TubeManagerConfig defaults to empty list and roundtrips via dict."""
    cfg = TubeManagerConfig()
    assert cfg.excluded_playlists == []

    cfg.excluded_playlists = ["PL123", "PL456"]
    stored = cfg.to_dict_for_storage()
    assert stored["excluded_playlists"] == ["PL123", "PL456"]

    loaded = TubeManagerConfig.from_dict(stored)
    assert loaded.excluded_playlists == ["PL123", "PL456"]


def test_tool_create_rule_new():
    """Verify _tool_create_rule creates a new AIRule and resolves title."""
    cfg = TubeManagerConfig()
    mock_yt = MagicMock()

    # Mock list_mine_playlists response
    mock_client = MagicMock()
    mock_client.list_mine_playlists.return_value = {
        "items": [
            {"id": "PL_AVA", "snippet": {"title": "Aviation"}},
            {"id": "PL_TECH", "snippet": {"title": "Tech"}},
        ]
    }
    mock_yt.get_client.return_value = mock_client

    # Call _tool_create_rule using target_playlist as title
    res = _tool_create_rule(
        config=cfg,
        youtube_service=mock_yt,
        name="Aviation rule",
        description="Route aircraft and dogfight videos to Aviation playlist",
        target_playlist="Aviation",
    )

    assert res["status"] == "created"
    assert res["target_playlist"] == "PL_AVA"
    assert res["playlist_name"] == "Aviation"
    assert len(cfg.ai_rules) == 1
    assert cfg.ai_rules[0].name == "Aviation rule"
    assert cfg.ai_rules[0].target_playlist == "PL_AVA"


def test_tool_create_rule_update_existing():
    """Verify _tool_create_rule updates an existing rule if target_playlist already has a rule."""
    cfg = TubeManagerConfig()
    existing = AIRule(
        name="Old Name",
        description="Old Description",
        target_playlist="PL_AVA",
        playlist_name="Aviation",
    )
    cfg.ai_rules.append(existing)

    mock_yt = MagicMock()
    res = _tool_create_rule(
        config=cfg,
        youtube_service=mock_yt,
        name="New Aviation Rule",
        description="Updated rule description",
        target_playlist="PL_AVA",
    )

    assert res["status"] == "updated"
    assert len(cfg.ai_rules) == 1
    assert cfg.ai_rules[0].name == "New Aviation Rule"
    assert cfg.ai_rules[0].description == "Updated rule description"


def test_apply_rules_filters_excluded_playlists():
    """Verify _tool_apply_rules skips excluded target/source playlists."""
    cfg = TubeManagerConfig()
    cfg.ai_rules.append(
        AIRule(
            name="Tech Rule",
            description="Route gadgets and tech videos to Tech",
            target_playlist="PL_TECH",
            playlist_name="Tech",
            enabled=True,
        )
    )
    cfg.excluded_playlists = ["PL_TECH"]  # Exclude target playlist

    mock_yt = MagicMock()
    mock_client = MagicMock()
    mock_client.list_mine_playlists.return_value = {
        "items": [
            {"id": "PL_TECH", "snippet": {"title": "Tech"}},
            {"id": "PL_UNSORTED", "snippet": {"title": "Unsorted"}},
        ]
    }
    mock_yt.get_client.return_value = mock_client

    res = _tool_apply_rules(config=cfg, youtube_service=mock_yt)
    # Target PL_TECH is excluded -> no proposed moves
    assert res["proposed_moves"] == []


def test_chat_agent_can_invoke_create_rule():
    """Verify run_chat drives create_rule tool when model requests it."""
    cfg = TubeManagerConfig()

    def simulate_provider(messages, tools):
        # Check if create_rule is advertised in tools
        tool_names = [t["name"] for t in tools]
        assert "create_rule" in tool_names

        # Return a tool call to create_rule
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "create_rule",
                                    "arguments": '{"name": "Gaming Rule", "description": "Route gaming videos", "target_playlist": "PL_GAME"}',
                                },
                            }
                        ],
                    }
                }
            ]
        }, "test/simulated"

    res = run_chat(
        message="Create a rule for gaming videos",
        config=cfg,
        simulate_provider=simulate_provider,
    )

    assert any(tc["name"] == "create_rule" for tc in res["tool_calls"])
    assert len(cfg.ai_rules) == 1
    assert cfg.ai_rules[0].name == "Gaming Rule"
    assert cfg.ai_rules[0].target_playlist == "PL_GAME"


@pytest.mark.asyncio
async def test_excluded_playlists_api_endpoints():
    """Verify GET, PUT/POST, and toggle endpoints for excluded playlists."""
    from app import get_excluded_playlists, update_excluded_playlists, toggle_excluded_playlist, ExcludedPlaylistsIn, ExcludedPlaylistToggleIn, config_manager

    # 1. Initially empty
    res = await get_excluded_playlists()
    assert "excluded_playlists" in res

    # 2. Update list
    res_update = await update_excluded_playlists(ExcludedPlaylistsIn(excluded_playlists=["PL_1", "PL_2"]))
    assert res_update["ok"] is True
    assert set(res_update["excluded_playlists"]) == {"PL_1", "PL_2"}

    # 3. Toggle off PL_1
    res_toggle = await toggle_excluded_playlist(ExcludedPlaylistToggleIn(playlist_id="PL_1"))
    assert res_toggle["status"] == "included"
    assert "PL_1" not in res_toggle["excluded_playlists"]

    # 4. Toggle on PL_3
    res_toggle2 = await toggle_excluded_playlist(ExcludedPlaylistToggleIn(playlist_id="PL_3"))
    assert res_toggle2["status"] == "excluded"
    assert "PL_3" in res_toggle2["excluded_playlists"]
