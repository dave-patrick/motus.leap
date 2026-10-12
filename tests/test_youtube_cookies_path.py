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