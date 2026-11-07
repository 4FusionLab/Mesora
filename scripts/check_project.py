"""Validate the initialized Fusion add-in and its release configuration."""

import argparse
import ast
import json
from pathlib import Path
import re
import uuid

ROOT = Path(__file__).resolve().parents[1]


def validate(root=ROOT, allow_template=False):
    root = Path(root)
    metadata = json.loads((root / '.fusion-addin.json').read_text(encoding='utf-8'))
    name = metadata['name']
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name):
        raise ValueError('Invalid add-in Python identifier.')
    initialized = metadata.get('initialized')
    if not isinstance(initialized, bool):
        raise ValueError('Metadata initialized flag must be boolean.')
    if not initialized and not allow_template:
        raise ValueError('Run the Initialize add-in workflow before releasing.')
    package = root / name
    if not package.is_dir() or not (package / (name + '.py')).is_file():
        raise ValueError('Missing Fusion Python entry point.')
    if not (package / '__init__.py').is_file():
        raise ValueError('Missing add-in package __init__.py.')
    manifest = json.loads((package / (name + '.manifest')).read_text(encoding='utf-8'))
    if manifest.get('type') != 'addin' or manifest.get('autodeskProduct') != 'Fusion360':
        raise ValueError('Invalid Fusion manifest type/product.')
    if manifest.get('supportedOS') != 'windows|mac':
        raise ValueError('Expected both Windows and macOS in the starter.')
    if not re.fullmatch(r'\d+\.\d+\.\d+', manifest.get('version', '')):
        raise ValueError('Invalid manifest numeric version.')
    if manifest.get('description', {}).get('') != metadata['description']:
        raise ValueError('Manifest description must match project metadata.')
    config = (package / 'config.py').read_text(encoding='utf-8')
    pure_code = ast.parse((package / 'core.py').read_text(encoding='utf-8'))
    for node in ast.walk(pure_code):
        if isinstance(node, ast.Import) and any(
            alias.name == 'adsk' or alias.name.startswith('adsk.') for alias in node.names
        ):
            raise ValueError('The testable domain core must not import Fusion APIs.')
        if isinstance(node, ast.ImportFrom) and node.module and (
            node.module == 'adsk' or node.module.startswith('adsk.')
        ):
            raise ValueError('The testable domain core must not import Fusion APIs.')
    if 'INITIALIZED = ' + str(initialized) not in config:
        raise ValueError('Fusion runtime initialization flag differs from metadata.')
    if 'ADDIN_NAME = ' + repr(name) not in config:
        raise ValueError('Fusion runtime add-in name differs from metadata.')
    uuid_value = str(uuid.UUID(manifest['id']))
    if initialized and uuid_value == '00000000-0000-4000-8000-000000000000':
        raise ValueError('A real project must generate its own UUID.')
    paths = (root / '.github/release-paths.txt').read_text(encoding='utf-8')
    if name + '/**' not in paths.splitlines():
        raise ValueError('Runtime release paths do not include the add-in package.')
    for filename in ('README.md', 'README.ru.md', 'AGENTS.md', 'GitVersion.yml'):
        if not (root / filename).is_file():
            raise ValueError('Missing repository contract: ' + filename)
    return name, initialized


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-template', action='store_true')
    parser.add_argument('--github-output', type=Path, help='Append CI outputs (product, initialized)')
    options = parser.parse_args()
    name, initialized = validate(allow_template=options.allow_template)
    print(f'Validated {name}; initialized={initialized}')
    if options.github_output:
        with options.github_output.open('a', encoding='utf-8') as stream:
            stream.write(f'product={name}\ninitialized={str(initialized).lower()}\n')


if __name__ == '__main__':
    main()
