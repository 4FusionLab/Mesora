"""Verify deterministic version stamping and checksums offline."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from scripts.build import build
from scripts.check_project import validate

ROOT = Path(__file__).resolve().parents[1]


class PackageTests(unittest.TestCase):
    def test_metadata_contract(self):
        product, initialized = validate(ROOT, allow_template=True)
        self.assertTrue(product)
        self.assertIsInstance(initialized, bool)

    def test_reproducible_zip_and_checksum(self):
        name = json.loads((ROOT / '.fusion-addin.json').read_text(encoding='utf-8'))['name']
        manifest_path = ROOT / name / (name + '.manifest')
        original = manifest_path.read_bytes()
        with TemporaryDirectory() as temp:
            archive, checksum = build(ROOT, '2.3.4', Path(temp), allow_template=True)
            first = archive.read_bytes()
            self.assertEqual(checksum.read_text(encoding='ascii'),
                             hashlib.sha256(first).hexdigest() + '  ' + archive.name + '\n')
            with zipfile.ZipFile(archive) as bundle:
                inner = json.loads(bundle.read(name + '/' + name + '.manifest'))
                self.assertEqual(inner['version'], '2.3.4')
                self.assertEqual(inner['type'], 'addin')
                self.assertIn(name + '/' + name + '.py', bundle.namelist())
                self.assertFalse(any('__pycache__' in entry or '.pyc' in entry
                                     for entry in bundle.namelist()))
            build(ROOT, '2.3.4', Path(temp), allow_template=True)
            self.assertEqual(first, archive.read_bytes())
        self.assertEqual(original, manifest_path.read_bytes())

    def test_requires_initialization_for_product_build(self):
        if not json.loads((ROOT / '.fusion-addin.json').read_text(encoding='utf-8'))['initialized']:
            with self.assertRaises(ValueError):
                with TemporaryDirectory() as temp:
                    build(ROOT, '0.1.0', Path(temp))


if __name__ == '__main__':
    unittest.main()
