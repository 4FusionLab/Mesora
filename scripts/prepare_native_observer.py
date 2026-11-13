"""Build an unshipped managed Fusion observer add-in for native acceptance.

Load the generated folder through Application.scripts.addExisting, then run(False).
Do not import/start the observer through an MCP script: that callback ownership
does not reproduce the Fusion-managed add-in lifecycle.
"""
import argparse
import json
from pathlib import Path
import shutil


NAME = 'MesoraAcceptanceObserver'
ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = '''"""Disposable read-only acceptance observer, loaded by Fusion Script Manager."""
from pathlib import Path
from . import observer


def run(context):
    observer.start(str(Path(__file__).parent / 'events.jsonl'))
    observer.probe()


def stop(context):
    result = observer.stop()
    if result.get('running'):
        raise RuntimeError('Observer could not detach all handlers')
'''


def prepare(output):
    folder = Path(output).resolve()
    if folder.name != NAME:
        raise ValueError('Output folder must be named ' + NAME)
    folder.mkdir(parents=True, exist_ok=True)
    # Never overwrite the event log: each managed run appends its session.
    shutil.copyfile(ROOT / 'scripts' / 'native_acceptance_observer.py', folder / 'observer.py')
    (folder / '__init__.py').write_text('', encoding='utf-8')
    (folder / (NAME + '.py')).write_text(ENTRYPOINT, encoding='utf-8')
    manifest = {'autodeskProduct': 'Fusion360', 'type': 'addin',
                'id': '2197dba9-6c78-48e0-bf24-652dbdf91570',
                'author': '4FusionLab', 'version': '0.0.1',
                'description': {'': 'Read-only native acceptance observer (development only).'},
                'supportedOS': 'windows|mac', 'editEnabled': True}
    (folder / (NAME + '.manifest')).write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'dist' / 'native-acceptance' / NAME)
    args = parser.parse_args()
    print(prepare(args.output))


if __name__ == '__main__':
    main()
