import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("mobile_oauth", Path(__file__).resolve().parents[2] / "core/mobile_oauth.py")
oauth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oauth)


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.store = oauth.MobileHandoffs()
        self.verifier = "a" * 43
        self.challenge = oauth.challenge_for(self.verifier)

    def issue(self):
        state = self.store.start(self.challenge, "b" * 43)
        entry = self.store.consume_state(state)
        return self.store.issue(entry, "test-token", 3600)

    def test_valid_redeem_is_single_use(self):
        code = self.issue()
        self.assertEqual(self.store.redeem(code, self.verifier)["access_token"], "test-token")
        with self.assertRaises(ValueError):
            self.store.redeem(code, self.verifier)

    def test_intercepted_code_needs_matching_verifier(self):
        code = self.issue()
        with self.assertRaises(ValueError):
            self.store.redeem(code, "c" * 43)
        self.assertEqual(self.store.redeem(code, self.verifier)["token_type"], "bearer")

    def test_state_cannot_be_replayed(self):
        state = self.store.start(self.challenge, "b" * 43)
        self.store.consume_state(state)
        with self.assertRaises(ValueError):
            self.store.consume_state(state)

    def test_expired_state_and_code_rejected(self):
        with patch.object(oauth.time, "monotonic", return_value=0):
            state = self.store.start(self.challenge, "b" * 43)
            code = self.issue()
        with patch.object(oauth.time, "monotonic", return_value=301):
            with self.assertRaises(ValueError):
                self.store.consume_state(state)
            with self.assertRaises(ValueError):
                self.store.redeem(code, self.verifier)

    def test_invalid_parameters_rejected(self):
        for challenge, state in [("bad", "b" * 43), (self.challenge, "bad")]:
            with self.assertRaises(ValueError):
                self.store.start(challenge, state)
        with self.assertRaises(ValueError):
            oauth.challenge_for("short")

    def test_rfc7636_s256_vector(self):
        self.assertEqual(oauth.challenge_for("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"),
                         "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")


if __name__ == "__main__":
    unittest.main()
