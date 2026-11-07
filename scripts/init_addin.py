"""One-time initializer for repositories created from the 4FusionLab template.

Creates fresh persistent Fusion identifiers and replaces the example package.
Safe to run locally or from the 'Initialize add-in' GitHub Actions workflow.
"""

import argparse
import json
from pathlib import Path
import re
import uuid

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER_UUID = '00000000-0000-4000-8000-000000000000'


def normalize_package_name(raw):
    """Convert an ordinary GitHub repo slug into a valid Python module name."""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError('A project/repository name is required.')
    parts = [part for part in re.split(r'[^A-Za-z0-9]+', raw.strip()) if part]
    if not parts or not parts[0][0].isalpha():
        raise ValueError('Name must start with an ASCII letter (try --name MyAddin).')
    name = ''.join(part[0].upper() + part[1:] for part in parts)
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name):
        raise ValueError('Invalid project name.')
    if len(name) > 60:
        raise ValueError('Project name is too long.')
    return name


def project_readme(name, display_name, description, repo, russian=False):
    link = 'README.md' if russian else 'README.ru.md'
    language = 'English' if russian else 'Русская версия'
    heading = f'# {display_name}\n\n[{language}]({link})\n\n{description}\n\n'
    if russian:
        body = (
            '## Статус\n\n'
            'Это начальный каркас 4FusionLab, а не готовая функциональность продукта. '
            'Команда в меню SOLID → ADD-INS показывает сообщение, не изменяя модель. '
            'Работу в реальном Autodesk Fusion нужно проверить отдельно.\n\n'
            '## Установка\n\n'
            f'Скачайте архив \'{name}-<version>.zip\' из Releases, распакуйте '
            f'папку \'{name}\' в каталог Fusion API AddIns, затем запустите аддин '
            'через Utilities → Add-Ins. Учитывайте версию Fusion и ОС.\n\n'
            '## Разработка\n\n'
            '- Бизнес-логика: \'<package>/core.py\' (без импорта adsk).\n'
            '- Fusion UI: \'<package>/<package>.py\'.\n'
            '- \'python -m unittest discover -s tests -v\' — offline-проверки.\n'
            '- \'python scripts/build.py --version 0.1.0\' — ZIP и SHA-256.\n'
            '- \'main\': релиз только при изменениях распространяемых файлов и зелёном CI.\n'
            '- Полный процесс: \'docs/DEVELOPMENT.md\'.\n'
        )
    else:
        body = (
            '## Status\n\n'
            'This is a 4FusionLab starter, not completed product functionality. '
            'Its SOLID → ADD-INS command shows a message without editing the model. '
            'Real Autodesk Fusion validation is required separately.\n\n'
            '## Installation\n\n'
            f'Download the versioned \'{name}-<version>.zip\' from Releases, extract '
            f'the \'{name}\' folder into the Fusion API AddIns directory, then '
            'start the add-in through Utilities → Add-Ins. Check your Fusion/OS version.\n\n'
            '## Development\n\n'
            '- Domain logic: \'<package>/core.py\' (no adsk imports).\n'
            '- Fusion UI: \'<package>/<package>.py\'.\n'
            '- \'python -m unittest discover -s tests -v\' runs offline tests.\n'
            '- \'python scripts/build.py --version 0.1.0\' builds ZIP and SHA-256.\n'
            '- Push/merge to \'main\' releases only for shipped input changes after green CI.\n'
            '- See \'docs/DEVELOPMENT.md\' for the full workflow.\n'
        )
    return heading + body.replace('<package>', name)


def initialize(root=ROOT, name='MyAddin', display_name=None, description=None, repo=None):
    root = Path(root)
    metadata_path = root / '.fusion-addin.json'
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    if metadata.get('initialized'):
        raise ValueError('This repository has already been initialized. Keep its UUIDs stable.')
    if metadata.get('name') != 'FusionAddin':
        raise ValueError('Unexpected template metadata; do not reinitialize an existing add-in.')
    name = normalize_package_name(name)
    display_name = (display_name or name).strip()
    description = (description or f'{display_name}: Autodesk Fusion add-in by 4FusionLab.').strip()
    if not display_name or not description:
        raise ValueError('Display name and description must not be empty.')
    if '\n' in display_name or '\n' in description:
        raise ValueError('Display name/description must be one line.')
    if repo is None:
        repo = '4FusionLab/' + name
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('Invalid GitHub owner/repository.')
    old = root / 'FusionAddin'
    target = root / name
    if not old.is_dir():
        raise ValueError('Template package is missing.')
    if name != 'FusionAddin' and target.exists():
        raise ValueError('Target add-in package already exists.')
    if name != 'FusionAddin':
        old.rename(target)
        (target / 'FusionAddin.py').rename(target / (name + '.py'))
        (target / 'FusionAddin.manifest').rename(target / (name + '.manifest'))

    manifest_path = target / (name + '.manifest')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('id') != PLACEHOLDER_UUID:
        raise ValueError('Manifest UUID was already changed: refusing to replace it.')
    manifest['id'] = str(uuid.uuid4())
    manifest['description'] = {'': description}
    manifest['author'] = '4FusionLab'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    command_id = '4FusionLab_' + name + '_' + uuid.uuid4().hex[:12]
    (target / 'config.py').write_text(
        '"""Stable 4FusionLab project identifiers; do not change after release."""\n\n'
        f'ADDIN_NAME = {name!r}\n'
        f'DISPLAY_NAME = {display_name!r}\n'
        f'DESCRIPTION = {description!r}\n'
        f'COMMAND_ID = {command_id!r}\n'
        'INITIALIZED = True\n',
        encoding='utf-8',
    )

    metadata.update(name=name, display_name=display_name, description=description, initialized=True)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (root / '.github/release-paths.txt').write_text(
        '# Only shipped add-in inputs may trigger an automatic GitHub Release.\n'
        f'{name}/**\n'
        'scripts/build.py\n'
        '.fusion-addin.json\n',
        encoding='utf-8',
    )
    for filename, russian in (('README.md', False), ('README.ru.md', True)):
        (root / filename).write_text(
            project_readme(name, display_name, description, repo, russian=russian),
            encoding='utf-8',
        )
    agents = root / 'AGENTS.md'
    agents.write_text(agents.read_text(encoding='utf-8').replace('FusionAddin', name), encoding='utf-8')
    initializer = root / '.github/workflows/initialize.yml'
    if initializer.exists():
        initializer.unlink()
    return {'name': name, 'manifest_id': manifest['id'], 'command_id': command_id, 'repo': repo}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True, help='Python package / GitHub repository slug')
    parser.add_argument('--display-name', help='Visible name inside Autodesk Fusion')
    parser.add_argument('--description', help='Short one-line product description')
    parser.add_argument('--repo', help='GitHub owner/repository, e.g. 4FusionLab/NewAddin')
    args = parser.parse_args()
    project = initialize(name=args.name, display_name=args.display_name,
                         description=args.description, repo=args.repo)
    print(f"Initialized {project['name']} with unique immutable Fusion IDs.")


if __name__ == '__main__':
    main()
