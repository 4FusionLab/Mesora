"""Smoke-test repository generation including UUID uniqueness."""

import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from scripts.check_project import validate
from scripts.init_addin import initialize, normalize_package_name

ROOT = Path(__file__).resolve().parents[1]
INITIALIZED = json.loads((ROOT / '.fusion-addin.json').read_text(encoding='utf-8'))['initialized']


class InitializationTests(unittest.TestCase):
    def test_name_normalization(self):
        self.assertEqual(normalize_package_name('shape-maker'), 'ShapeMaker')
        self.assertEqual(normalize_package_name('filamentra'), 'Filamentra')
        with self.assertRaises(ValueError):
            normalize_package_name('3d-addon')

    @unittest.skipIf(INITIALIZED, 'Template-only integration test')
    def test_generated_project_is_standalone(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(ROOT / 'FusionAddin', root / 'FusionAddin')
            (root / 'scripts').mkdir()
            (root / '.github/workflows').mkdir(parents=True)
            for filename in ('.fusion-addin.json', 'README.md', 'README.ru.md',
                             'AGENTS.md', 'GitVersion.yml'):
                shutil.copyfile(ROOT / filename, root / filename)
            shutil.copyfile(ROOT / '.github/release-paths.txt',
                            root / '.github/release-paths.txt')
            shutil.copyfile(ROOT / '.github/workflows/initialize.yml',
                            root / '.github/workflows/initialize.yml')
            result = initialize(root, 'Shape-Maker', 'Shape Maker', 'CAD utility', '4FusionLab/Shape-Maker')
            self.assertEqual(result['name'], 'ShapeMaker')
            self.assertEqual(validate(root), ('ShapeMaker', True))
            self.assertFalse((root / 'FusionAddin').exists())
            self.assertTrue((root / 'ShapeMaker/ShapeMaker.py').is_file())
            self.assertFalse((root / '.github/workflows/initialize.yml').exists())
            self.assertNotEqual(result['manifest_id'], '00000000-0000-4000-8000-000000000000')
            with self.assertRaises(ValueError):
                initialize(root, 'Another')


if __name__ == '__main__':
    unittest.main()
