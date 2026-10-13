"""Unit tests for POST /api/import-yt-cookies on the deployed app (app:app).

The endpoint must persist an exported Netscape cookie file to the durable
Playwright cookie store (core.actions.get_youtube_cookies_path()) and must not
depend on the legacy Camofox service.
"""
import contextlib
import json
import os
import secrets
import tempfile
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("TUBE_MANAGER_DATA_DIR", tempfile.mkdtemp(prefix="motus_cookie_import_test_"))
os.environ["TUBE_MANAGER_SECRET_KEY"] = os.environ.get(
    "TUBE_MANAGER_SECRET_KEY", "test_secret_key_for_cookie_import_tests"
)

from api.auth import create_access_token

NETSCAPE = (
    "# Netscape HTTP Cookie File\n"
    ".youtube.com\tTRUE\t/\tTRUE\t1893456000\tSID\tsecret-sid\n"
    "#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t1893456000\tHSID\tsecret-hsid\n"
    ".example.com\tTRUE\t/\tFALSE\t1893456000\tOTHER\tnot-youtube\n"
)

# A complete set of the login cookies a signed-in youtube.com export carries.
SIGNED_IN_NETSCAPE = (
    "# Netscape HTTP Cookie File\n"
    ".youtube.com\tTRUE\t/\tTRUE\t1893456000\tSID\tsid\n"
    "#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t1893456000\tHSID\thsid\n"
    ".youtube.com\tTRUE\t/\tTRUE\t1893456000\tSSID\tssid\n"
    ".youtube.com\tTRUE\t/\tTRUE\t1893456000\tAPISID\tapisid\n"
    ".youtube.com\tTRUE\t/\tTRUE\t1893456000\tSAPISID\tsapisid\n"
    "#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t1893456000\t__Secure-1PSID\tpsid1\n"
    "#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t1893456000\t__Secure-3PSID\tpsid3\n"
    "#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t1893456000\tLOGIN_INFO\tlogininfo\n"
)


@pytest.mark.unit
class TestImportYTCookiesEndpoint:
    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch, tmp_path):
        import app as app_module
        from api import auth as auth_module

        users_db = {
            "ctest": {
                "id": secrets.token_hex(8),
                "username": "ctest",
                "email": "ctest@example.com",
                "hashed_password": "x",
                "role": "admin",
                "is_active": True,
                "created_at": datetime.now(),
                "last_login": None,
            }
        }
        monkeypatch.setattr(auth_module, "_cached_users_db", users_db)
        auth_module._cached_users_db = users_db

        token = create_access_token({"sub": "ctest"})
        self.auth_headers = {"Authorization": f"Bearer {token}"}

        # Point the cookie resolver at a temp store so the test never touches the
        # real profile (this dev box has a legacy ~/.camofox fallback on disk).
        self.store = tmp_path / "cookies" / "youtube_cookies.json"
        monkeypatch.setenv("YOUTUBE_COOKIES_FILE", str(self.store))
        monkeypatch.setenv("TUBE_MANAGER_DATA_DIR", str(tmp_path))
        monkeypatch.delenv("CAMOFOX_URL", raising=False)

        app_module.app.router.lifespan_context = contextlib.asynccontextmanager(
            lambda a: (yield)
        )
        self.client = TestClient(
            app_module.app,
            base_url="http://localhost:8000",
            headers={"Origin": "http://localhost:8000"},
        )

    def _post(self, text):
        return self.client.post(
            "/api/import-yt-cookies",
            json={"cookies_txt": text},
            headers=self.auth_headers,
        )

    def test_writes_to_persistent_store(self):
        r = self._post(NETSCAPE)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        assert body["count"] == 2

        assert self.store.exists(), "cookie store must be written where the driver reads"
        assert body["path"] == str(self.store)

        data = json.loads(self.store.read_text(encoding="utf-8"))
        assert {c["name"] for c in data} == {"SID", "HSID"}
        assert all("youtube" in c["domain"] for c in data)
        hs = next(c for c in data if c["name"] == "HSID")
        assert hs["httpOnly"] is True
        assert hs["secure"] is True

    def test_mirrors_netscape_copy(self):
        self._post(NETSCAPE)
        mirror = self.store.parent / "youtube_cookies.txt"
        assert mirror.exists()
        assert "secret-sid" in mirror.read_text(encoding="utf-8")

    def test_no_camofox_service_is_not_fatal(self):
        # CAMOFOX_URL is unset, so the import must succeed without any Camofox call.
        r = self._post(NETSCAPE)
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_rejects_empty_input(self):
        r = self._post("")
        assert r.status_code == 400
        assert "No valid cookies" in r.json()["detail"]

    def test_rejects_non_youtube_cookies(self):
        r = self._post("# Netscape HTTP Cookie File\n.example.com\tTRUE\t/\tFALSE\t0\tOTHER\tx\n")
        assert r.status_code == 400
        assert "YouTube/Google" in r.json()["detail"]

    def test_warns_when_the_export_has_no_login_cookies(self):
        # NETSCAPE has SID and HSID but none of the other login cookies, which is
        # what a signed-out youtube.com export looks like. The import still lands
        # so the user can fix the browser and retry; the response says why.
        r = self._post(NETSCAPE)
        body = r.json()
        assert r.status_code == 200
        assert body["success"] is True
        assert body["count"] == 2
        assert body["signed_in"] is False
        assert body["warning"]
        assert "signed-out youtube.com page" in body["warning"]
        assert "signed-out youtube.com page" in body["message"]

    def test_reports_a_signed_in_export(self, monkeypatch):
        import services.youtube_innertube as innertube

        monkeypatch.setattr(
            innertube,
            "check_watch_later_session",
            lambda *args, **kwargs: {
                "signed_in": True,
                "message": "The cookies open a signed-in YouTube session.",
            },
        )
        r = self._post(SIGNED_IN_NETSCAPE)
        body = r.json()
        assert r.status_code == 200
        assert body["signed_in"] is True
        assert body["warning"] is None
        assert body["message"].startswith("Imported 8 cookies.")

    def test_warns_when_the_session_check_says_signed_out(self, monkeypatch):
        import services.youtube_innertube as innertube

        monkeypatch.setattr(
            innertube,
            "check_watch_later_session",
            lambda *args, **kwargs: {
                "signed_in": False,
                "message": "The stored YouTube cookies are no longer signed in.",
            },
        )
        r = self._post(SIGNED_IN_NETSCAPE)
        body = r.json()
        assert r.status_code == 200
        assert body["success"] is True
        assert body["signed_in"] is False
        assert body["warning"] == "The stored YouTube cookies are no longer signed in."
        assert "no longer signed in" in body["message"]
