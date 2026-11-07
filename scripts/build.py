"""Reproducible, installable Fusion add-in archive and SHA-256 checksum."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z')
SKIP_DIRS = {'__pycache__', '.git', '.venv', 'node_modules'}
SKIP_FILES = {'.DS_Store'}
FORBIDDEN_SUFFIXES = {'.pyc', '.pyo', '.pem', '.p12', '.pfx', '.key'}
FORBIDDEN_NAMES = {'.env', '.env.local', '.env.production'}


def candidate_files(directory):
    """Include only installed add-in contents; reject symlinks and obvious secrets."""
    if directory.is_symlink():
        raise ValueError('Symlinked add-in directory is forbidden.')
    result = []
    for path in sorted(directory.rglob('*')):
        relative = path.relative_to(directory)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError('Symlinks are forbidden in a Fusion add-in ZIP: ' + str(path))
        if not path.is_file():
            continue
        if path.name in SKIP_FILES or path.suffix.lower() in {'.pyc', '.pyo'}:
            continue
        if path.name.lower() in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            raise ValueError('Potentially sensitive file cannot be packaged: ' + str(path))
        if any(part.startswith('.') for part in relative.parts):
            raise ValueError('Hidden files are not package inputs: ' + str(path))
        result.append(path)
    return result


def build(root=ROOT, version='0.1.0', output=None, allow_template=False):
    root = Path(root).resolve()
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError('Expected numeric MAJOR.MINOR.PATCH version.')
    metadata = json.loads((root / '.fusion-addin.json').read_text(encoding='utf-8'))
    if not metadata.get('initialized') and not allow_template:
        raise ValueError('Initialize this template before building a release.')
    name = metadata['name']
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name):
        raise ValueError('Invalid Python add-in package identifier.')
    directory = root / name
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError('Add-in package directory is missing.')
    manifest_path = directory / (name + '.manifest')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('autodeskProduct') != 'Fusion360' or manifest.get('type') != 'addin':
        raise ValueError('Not a Fusion add-in manifest.')
    manifest['version'] = version

    output = Path(output) if output is not None else root / 'dist'
    output.mkdir(parents=True, exist_ok=True)
    archive = output / (name + '-' + version + '.zip')
    files = candidate_files(directory)
    if manifest_path not in files or directory / (name + '.py') not in files:
        raise ValueError('The add-in entry point or manifest is missing.')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as bundle:
        for path in files:
            member = name + '/' + path.relative_to(directory).as_posix()
            data = path.read_bytes()
            if path == manifest_path:
                data = (json.dumps(manifest, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
            info = zipfile.ZipInfo(member, date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, data)
    checksum = archive.with_suffix('.zip.sha256')
    checksum.write_text(
        hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n',
        encoding='ascii',
    )
    return archive, checksum


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='0.1.0')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--allow-template', action='store_true',
                        help='Only for testing the uninitialized starter, never for publishing')
    options = parser.parse_args()
    for path in build(version=options.version, output=options.output,
                      allow_template=options.allow_template):
        print(path)


if __name__ == '__main__':
    main()
