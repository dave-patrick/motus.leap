import pytest
from services.playlist_protection import (
    is_video_protected_in_current_playlist,
    is_playlist_opted_in,
    is_staging_playlist,
    TOPIC_KEYWORDS,
)
from models.config import AIRule, TubeManagerConfig


class TestPlaylistProtection:
    def test_staging_playlists_are_never_protected(self):
        assert is_video_protected_in_current_playlist(
            "Star Wars Episode 1", "pl_sort", "1~Sort", "pl_sw", "Star Wars"
        ) is False
        assert is_video_protected_in_current_playlist(
            "Star Wars Episode 1", "pl_inbox", "Inbox", "pl_sw", "Star Wars"
        ) is False
        assert is_video_protected_in_current_playlist(
            "Star Wars Episode 1", "pl_wl", "Watch Later", "pl_sw", "Star Wars"
        ) is False

    def test_star_wars_lore_protected_in_star_wars(self):
        # The user's exact cases from the screenshot
        assert is_video_protected_in_current_playlist(
            "Star Wars Legends: Force Storm — Episode 1", "pl_sw", "Star Wars", "pl_ai", "AI"
        ) is True
        assert is_video_protected_in_current_playlist(
            "Ahsoka Season 2 Teaser Trailer BREAKDOWN", "pl_sw", "Star Wars", "pl_cos", "Cosplay"
        ) is True
        assert is_video_protected_in_current_playlist(
            "Dawn of the Jedi: Into the Void 5", "pl_sw", "Star Wars", "pl_ai", "AI"
        ) is True
        assert is_video_protected_in_current_playlist(
            "Star Wars Visions Presents : The Ninth Jedi - Full Series Review", "pl_sw", "Star Wars", "pl_cos", "Cosplay"
        ) is True

    def test_star_wars_exceptions_allowed(self):
        # User specified: UNLESS it is a music video or cosplay video
        assert is_video_protected_in_current_playlist(
            "Star Wars Imperial March Official Music Video", "pl_sw", "Star Wars", "pl_mv", "Music Videos"
        ) is False
        assert is_video_protected_in_current_playlist(
            "Star Wars Celebration Cosplay Showcase 2024", "pl_sw", "Star Wars", "pl_cos", "Cosplay"
        ) is False

    def test_other_playlists_protected(self):
        # Aviation
        assert is_video_protected_in_current_playlist(
            "F-16 Dogfight Combat Footage Over Pacific", "pl_av", "Aviation", "pl_tech", "Tech"
        ) is True
        # Woodworking
        assert is_video_protected_in_current_playlist(
            "How to Build a Dining Table with Hand Tools", "pl_ww", "Woodworking", "pl_maker", "Maker"
        ) is True
        # Bigfoot
        assert is_video_protected_in_current_playlist(
            "Bigfoot Caught on Camera in Washington State", "pl_bf", "Bigfoot", "pl_learn", "Learning"
        ) is True
        # Truck
        assert is_video_protected_in_current_playlist(
            "2024 Toyota Tacoma TRD Pro Off-Road Test", "pl_tr", "Truck", "pl_auto", "Auto"
        ) is True
        # Food
        assert is_video_protected_in_current_playlist(
            "Air Fryer Ribeye Steak Recipe That Melts in Your Mouth", "pl_food", "Food", "pl_ent", "Entertainment"
        ) is True
        # Drones
        assert is_video_protected_in_current_playlist(
            "DJI Avata 2 FPV Drone Mountain Dive", "pl_dr", "Drones", "pl_tech", "Tech"
        ) is True

    def test_config_ai_rules_custom_keywords_honored(self):
        cfg = TubeManagerConfig()
        cfg.ai_rules = [
            AIRule(
                name="Custom Retro Rule",
                description="Retro gaming consoles, Nintendo 64, SNES, and Sega Genesis",
                target_playlist="pl_retro",
                playlist_name="Retro Gaming"
            )
        ]
        assert is_video_protected_in_current_playlist(
            "Top 10 Nintendo 64 Hidden Gems", "pl_retro", "Retro Gaming", "pl_tech", "Tech", config=cfg
        ) is True

    def test_playlist_opt_in_logic(self):
        # Staging playlists are always opted in
        assert is_playlist_opted_in("pl_sort", "1~Sort", []) is True
        assert is_playlist_opted_in("pl_inbox", "Inbox", []) is True
        assert is_playlist_opted_in("pl_sort", "1~Sort", ["Other"]) is True

        # Unconfigured opt_in_list allows all playlists (protection handled by is_video_protected_in_current_playlist)
        assert is_playlist_opted_in("pl_sw", "Star Wars", []) is True
        assert is_playlist_opted_in("pl_av", "Aviation", []) is True

        # Configured opt_in_list restricts non-staging playlists strictly to selected ones
        assert is_playlist_opted_in("pl_sw", "Star Wars", ["Aviation"]) is False
        assert is_playlist_opted_in("pl_sw", "Star Wars", ["Star Wars"]) is True
        assert is_playlist_opted_in("pl_sw", "Star Wars", ["pl_sw"]) is True