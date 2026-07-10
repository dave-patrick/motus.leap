"""
M2 regression: CSRF/origin validation for the *.onrender.com deployment.

`verify_origin` must ACCEPT the app's real Render origin (it is in the
ALLOWED_ORIGINS allow-list) and REJECT a foreign origin — including an
arbitrary attacker-controlled *.onrender.com subdomain, which the old wildcard
`origin.endswith(".onrender.com")` check incorrectly trusted.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

os.environ.setdefault("TUBE_MANAGER_DATA_DIR", tempfile.mkdtemp(prefix="motus_m2_test_"))

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import HTTPException
from api.auth import verify_origin, ALLOWED_ORIGINS


def _request(origin=None, referer=None):
    headers = {}
    if origin is not None:
        headers["origin"] = origin
    if referer is not None:
        headers["referer"] = referer
    req = Mock()
    req.headers = headers
    req.cookies = {}
    return req


@pytest.mark.security
class TestM2CsrfOrigin:
    @pytest.mark.asyncio
    async def test_accepts_onrender_origin(self):
        """The deployed Render origin (in the allow-list) is accepted."""
        onrender = next(o for o in ALLOWED_ORIGINS if o.endswith(".onrender.com"))
        # Should not raise.
        await verify_origin(_request(origin=onrender))

    @pytest.mark.asyncio
    async def test_rejects_foreign_origin(self):
        """A completely foreign origin is rejected with 403."""
        with pytest.raises(HTTPException) as exc:
            await verify_origin(_request(origin="https://evil.example.com"))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_rejects_attacker_onrender_subdomain(self):
        """An arbitrary attacker *.onrender.com subdomain is NOT trusted (M2 fix)."""
        with pytest.raises(HTTPException) as exc:
            await verify_origin(_request(origin="https://attacker-evil.onrender.com"))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_accepts_onrender_referer(self):
        """Same-origin POST (no Origin header) validated via referer host."""
        onrender = next(o for o in ALLOWED_ORIGINS if o.endswith(".onrender.com"))
        await verify_origin(_request(referer=f"{onrender}/dashboard"))

    @pytest.mark.asyncio
    async def test_rejects_foreign_referer(self):
        with pytest.raises(HTTPException) as exc:
            await verify_origin(_request(referer="https://evil.example.com/x"))
        assert exc.value.status_code == 403
