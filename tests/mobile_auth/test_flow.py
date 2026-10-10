"""Route-level OAuth tests; Google responses and persistence are isolated."""
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root if (root / 'api/auth.py').exists() else root / 'tube-manager'))
os.environ.setdefault('TUBE_MANAGER_DATA_DIR', tempfile.mkdtemp(prefix='motus-mobile-test-'))
os.environ.setdefault('TUBE_MANAGER_SECRET_KEY', 'isolated-test-secret-not-for-production')
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api import auth
from core.mobile_oauth import challenge_for, MobileHandoffs


class FlowTests(unittest.TestCase):
    def setUp(self):
        auth.mobile_handoffs = MobileHandoffs()
        self.app = FastAPI()
        self.app.state.limiter = auth.limiter
        self.app.include_router(auth.router)
        self.users_dependency = auth.get_users_db
        self.client = TestClient(self.app)
        self.verifier = 'a' * 43

    def test_browser_handoff_exchange_and_authenticated_request(self):
        user = {'id': 'test-user', 'username': 'test', 'email': 'test@example.com',
                'role': 'user', 'is_active': True, 'created_at': datetime.now(), 'last_login': None}
        google = AsyncMock()
        google.__aenter__.return_value = google
        class Reply:
            def __init__(self, payload): self.payload = payload
            def json(self): return self.payload
        google.post.return_value = Reply({'access_token': 'mock-google-token'})
        google.get.return_value = Reply({'email': 'test@example.com', 'name': 'Test', 'verified_email': True})
        with patch.object(auth, 'GOOGLE_OAUTH_CLIENT_ID', 'test-client'), \
             patch.object(auth, 'GOOGLE_OAUTH_CLIENT_SECRET', 'test-secret'), \
             patch.object(auth, 'get_users_db', AsyncMock(return_value={'test': user})), \
             patch.object(auth, '_save_users', AsyncMock()), \
             patch.object(auth, '_save_sessions', AsyncMock()):
            # Newer deployment code resolves credentials dynamically.
            resolver = patch.object(auth, '_resolve_oauth_credentials', return_value=('test-client', 'test-secret'), create=True)
            with resolver:
                start = self.client.get('/api/auth/mobile/google', params={'code_challenge': challenge_for(self.verifier), 'client_state': 'b' * 43})
                self.assertEqual(start.status_code, 200)
                state = parse_qs(urlparse(start.json()['auth_url']).query)['state'][0]
                with patch.object(auth.httpx, 'AsyncClient', return_value=google):
                    callback = self.client.get('/api/auth/google/callback', params={'code': 'mock-code', 'state': state}, follow_redirects=False)
                self.assertEqual(callback.status_code, 302)
                location = urlparse(callback.headers['location'])
                self.assertEqual(location.scheme, 'motusleap')
                self.assertNotIn('token', callback.headers['location'])
                query = parse_qs(location.query)
                self.assertEqual(query['state'][0], 'b' * 43)
                body = {'code': query['code'][0], 'code_verifier': self.verifier}
                exchange = self.client.post('/api/auth/mobile/exchange', json=body)
                self.assertEqual(exchange.status_code, 200)
                self.assertEqual(exchange.headers['cache-control'], 'no-store')
                self.assertEqual(self.client.post('/api/auth/mobile/exchange', json=body).status_code, 400)
                self.app.dependency_overrides[self.users_dependency] = lambda: {'test': user}
                me = self.client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + exchange.json()['access_token']})
                self.assertEqual(me.status_code, 200)
                self.assertEqual(me.json()['username'], 'test')

    def test_unknown_mobile_callback_state_is_rejected(self):
        response = self.client.get('/api/auth/google/callback', params={'code': 'unused', 'state': 'mobile_unknown'})
        self.assertEqual(response.status_code, 400)

    def test_bad_exchange_is_rejected(self):
        response = self.client.post('/api/auth/mobile/exchange', json={'code': 'unused', 'code_verifier': 'a' * 43})
        self.assertEqual(response.status_code, 400)


if __name__ == '__main__': unittest.main()
