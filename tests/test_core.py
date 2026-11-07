"""The domain core is importable without Autodesk Fusion installed."""

import importlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        metadata = json.loads((ROOT / '.fusion-addin.json').read_text(encoding='utf-8'))
        cls.core = importlib.import_module(metadata['name'] + '.core')

    def test_document_context(self):
        self.assertIn('Example.f3d', self.core.ready_message('Sample', 'Example.f3d'))

    def test_no_document(self):
        self.assertIn('Open a design', self.core.ready_message('Sample', None))

    def test_missing_display_name(self):
        with self.assertRaises(ValueError):
            self.core.ready_message('', 'Example.f3d')


if __name__ == '__main__':
    unittest.main()
