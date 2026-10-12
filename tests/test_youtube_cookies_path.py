import core.actions as actions


def test_uses_env_override(tmp_path, monkeypatch):
    override = tmp_path / "override.json"
    override.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("YOUTUBE_COOKIES_FILE", str(override))
    assert actions.get_youtube_cookies_path() == str(override)


def test_prefers_persistent_data_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("YOUTUBE_COOKIES_FILE", raising=False)
    monkeypatch.setenv("TUBE_MANAGER_DATA_DIR", str(tmp_path))
    cookies_dir = tmp_path / "cookies"
    cookies_dir.mkdir()
    store = cookies_dir / "youtube_cookies.json"
    store.write_text("[]", encoding="utf-8")
    assert actions.get_youtube_cookies_path() == str(store)


def test_falls_back_to_legacy_camofox_path(tmp_path, monkeypatch):
    monkeypatch.delenv("YOUTUBE_COOKIES_FILE", raising=False)
    monkeypatch.setenv("TUBE_MANAGER_DATA_DIR", str(tmp_path))
    legacy = actions.os.path.expanduser("~/.camofox/cookies/cookies.json")
    assert actions.get_youtube_cookies_path() in {legacy, str(tmp_path / "cookies" / "youtube_cookies.json")}

def test_write_path_prefers_data_dir_over_legacy(tmp_path, monkeypatch):
    monkeypatch.delenv("YOUTUBE_COOKIES_FILE", raising=False)
    monkeypatch.setenv("TUBE_MANAGER_DATA_DIR", str(tmp_path))
    assert actions.get_youtube_cookies_write_path() == str(tmp_path / "cookies" / "youtube_cookies.json")


def test_write_path_honours_env_override(tmp_path, monkeypatch):
    override = tmp_path / "override.json"
    monkeypatch.setenv("YOUTUBE_COOKIES_FILE", str(override))
    monkeypatch.setenv("TUBE_MANAGER_DATA_DIR", str(tmp_path))
    assert actions.get_youtube_cookies_write_path() == str(override)


def test_write_path_ignores_a_stale_existing_store(tmp_path, monkeypatch):
    """An import must land at the durable path even if an older store already exists."""
    monkeypatch.setenv("TUBE_MANAGER_DATA_DIR", str(tmp_path))
    legacy = tmp_path / "legacy.json"
    legacy.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("YOUTUBE_COOKIES_FILE", str(legacy))
    monkeypatch.delenv("YOUTUBE_COOKIES_FILE", raising=False)
    monkeypatch.setattr(actions.os.path, "expanduser", lambda p: str(legacy))
    assert actions.get_youtube_cookies_write_path() == str(tmp_path / "cookies" / "youtube_cookies.json")