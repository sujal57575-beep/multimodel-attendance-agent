"""
tests/test_sessions.py — Session API unit tests
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
from config import Config
from models.database import init_db

# Use temp file SQLite for tests
_test_db = os.path.join(tempfile.gettempdir(), "test_attend_sessions.db")
if os.path.exists(_test_db):
    try: os.remove(_test_db)
    except Exception: pass
os.environ["DATABASE_PATH"] = _test_db
Config.DATABASE_PATH = _test_db
init_db()

from app import create_app


class SessionAPITest(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.app.testing = True

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(_test_db):
            try: os.remove(_test_db)
            except Exception: pass

    def test_health(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertEqual(data["status"], "ok")

    def test_create_session(self):
        r = self.client.post(
            "/api/sessions",
            data=json.dumps({"name": "Test Session", "subject": "AI"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)
        data = json.loads(r.data)
        self.assertIn("session_id", data)
        return data["session_id"]

    def test_create_session_missing_name(self):
        r = self.client.post(
            "/api/sessions",
            data=json.dumps({"subject": "Math"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)

    def test_get_sessions(self):
        r = self.client.get("/api/sessions")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn("sessions", data)

    def test_get_nonexistent_session(self):
        r = self.client.get("/api/sessions/doesnotexist")
        self.assertEqual(r.status_code, 404)

    def test_delete_session(self):
        sid = self.test_create_session()
        r = self.client.delete(f"/api/sessions/{sid}")
        self.assertEqual(r.status_code, 200)
        r2 = self.client.get(f"/api/sessions/{sid}")
        self.assertEqual(r2.status_code, 404)


if __name__ == "__main__":
    unittest.main()
