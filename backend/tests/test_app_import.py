import os
import tempfile
import unittest

os.environ.setdefault("IMAGEVIEWER_DATA", tempfile.mkdtemp(prefix="photolibrary-test-"))

from app.main import app, health


class AppImportTests(unittest.TestCase):
    def test_health_endpoint_is_registered(self):
        route = next(
            (route for route in app.routes if getattr(route, "path", None) == "/api/health"),
            None,
        )

        self.assertIsNotNone(route)
        self.assertIs(route.endpoint, health)
        self.assertEqual(health(), {"ok": True})
