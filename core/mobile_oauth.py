"""Short-lived, single-use Android OAuth handoffs protected with S256 PKCE.

The current deployment uses a single API process. Multiple replicas require a
shared handoff store. No Google token or application token is placed in a URL.
"""
import base64
import hashlib
import re
import secrets
import time


def challenge_for(verifier: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", verifier):
        raise ValueError("Invalid code verifier")
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")


class MobileHandoffs:
    def __init__(self):
        self.states = {}
        self.codes = {}

    def _prune(self):
        now = time.monotonic()
        for store in (self.states, self.codes):
            for key, value in list(store.items()):
                if value["expires"] <= now:
                    store.pop(key, None)

    def start(self, challenge: str, client_state: str) -> str:
        self._prune()
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", challenge):
            raise ValueError("S256 code challenge required")
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", client_state):
            raise ValueError("Invalid client state")
        if len(self.states) + len(self.codes) >= 1000:
            raise ValueError("Too many sign-in attempts; try again later")
        state = "mobile_" + secrets.token_urlsafe(32)
        self.states[state] = {"challenge": challenge, "client_state": client_state,
                              "expires": time.monotonic() + 300}
        return state

    def consume_state(self, state: str) -> dict:
        self._prune()
        entry = self.states.pop(state, None)
        if entry is None:
            raise ValueError("Sign-in expired or was already used")
        return entry

    def issue(self, entry: dict, token: str, expires_in: int) -> str:
        self._prune()
        code = secrets.token_urlsafe(32)
        self.codes[code] = {**entry, "token": token, "expires_in": expires_in,
                            "expires": time.monotonic() + 60}
        return code

    def redeem(self, code: str, verifier: str) -> dict:
        self._prune()
        entry = self.codes.get(code)
        if entry is None or not secrets.compare_digest(entry["challenge"], challenge_for(verifier)):
            raise ValueError("Invalid or expired sign-in code")
        self.codes.pop(code)
        return {"access_token": entry["token"], "token_type": "bearer", "expires_in": entry["expires_in"]}
