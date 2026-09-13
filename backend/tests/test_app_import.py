import os
import tempfile
import unittest

os.environ.setdefault("IMAGEVIEWER_DATA", tempfile.mkdtemp(prefix="photolibrary-test-"))

from fastapi.testclient import TestClient

from app.main import app


class AppImportTests(unittest.TestCase):
    def test_health_endpoint(self):
        with TestClient(app) as client:
            response = client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
