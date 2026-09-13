import unittest

from app.main import app


class AppImportTests(unittest.TestCase):
    def test_application_imports(self):
        self.assertEqual(app.title, "PhotoLibrary Viewer")
