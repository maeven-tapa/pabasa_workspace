"""Replace source masters with a previously measured compact image profile.

Run without --apply for a preflight. An ignored ZIP backup is required before
replacement. Never traverses uploads or other source directories.
"""
import argparse
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image

from optimize_static_images import sized_png


REPOSITORY = Path(__file__).resolve().parents[1]
SOURCE = REPOSITORY / 'pabasa_site/pabasa_app/static'
ALIASES = REPOSITORY / 'pabasa_site/pabasa_app/static_image_aliases.json'


def replacement_plan(report, variants_root):
    plan = []
    destinations = set()
    for row in report['images']:
        relative = Path(row['path'])
        original = (SOURCE / relative).resolve()
        if SOURCE.resolve() not in original.parents or 'uploads' in relative.parts:
            raise ValueError('Image outside application asset scope')
        master = original.read_bytes()
        if len(master) != row['original_bytes'] or master != (variants_root / relative).read_bytes():
            raise ValueError(f'Source changed since compact measurement: {relative}')
        if not row['optimized']:
            continue
        codec = min(row['variants'], key=lambda name: row['variants'][name]['bytes'])
        if relative.as_posix() == 'pabasa_app/images/pabasa_logo.png':
            # HTML email clients still need PNG. Keep the same compact dimensions.
            destination = original
            payload = sized_png(master, 1024)
            codec = 'png'
        else:
            svg = original.suffix.lower() == '.svg'
            sidecar = ('.optimized.png' if codec == 'png' else
                       f'.{codec}' + ('.svg' if svg else ''))
            payload = (variants_root / relative).with_name(relative.name + sidecar).read_bytes()
            if len(payload) != row['variants'][codec]['bytes']:
                raise ValueError(f'Variant differs from measurement: {relative}')
            destination = original if svg or codec == 'png' else original.with_suffix('.' + codec)
        if not payload or len(payload) >= len(master):
            raise ValueError(f'Replacement is not smaller: {relative}')
        if destination != original and (destination in destinations or destination.exists()):
            # Some lessons have both name.png and name.jpg; preserve their identity.
            destination = original.with_name(original.name + '.' + codec)
        if destination in destinations or destination != original and destination.exists():
            raise ValueError(f'Image filename collision: {destination.name}')
        destinations.add(destination)
        if destination.suffix.lower() == '.svg':
            import xml.etree.ElementTree as ET
            ET.fromstring(payload)
        else:
            with Image.open(BytesIO(payload)) as decoded:
                decoded.load()
                if decoded.format.lower() != codec:
                    raise ValueError(f'Image format mismatch: {relative}')
        plan.append((original, destination, payload))
    return plan


def apply_replacements(plan, backup):
    if backup.exists() or SOURCE.resolve() in backup.resolve().parents:
        raise ValueError('Use a new backup file outside the source static directory')
    backup.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(backup, 'x', compression=ZIP_DEFLATED, compresslevel=1) as archive:
        for original, _, _ in plan:
            archive.write(original, original.relative_to(SOURCE).as_posix())
    with ZipFile(backup) as archive:
        if archive.testzip() is not None:
            raise ValueError('Original image backup verification failed')
    aliases = {original.relative_to(SOURCE).as_posix(): destination.relative_to(SOURCE).as_posix()
               for original, destination, _ in plan if original != destination}
    for original, destination, payload in plan:
        temporary = destination.with_name(destination.name + '.replacement-tmp')
        temporary.write_bytes(payload)
        # Atomic replacement also avoids overwriting any hardlinked QA masters.
        temporary.replace(destination)
    ALIASES.write_text(json.dumps(aliases, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    for original, destination, _ in plan:
        if original != destination:
            original.unlink()
    return aliases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--variants-root', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding='utf-8'))
    if report.get('profile') != 'compact':
        parser.error('Replacement requires the measured compact profile')
    plan = replacement_plan(report, args.variants_root.resolve())
    saved = sum(original.stat().st_size - len(payload) for original, _, payload in plan)
    print(json.dumps(dict(replacements=len(plan), original_image_bytes=report['original_image_bytes'],
                          replacement_image_bytes=report['original_image_bytes'] - saved,
                          saved_bytes=saved, apply=args.apply), indent=2), flush=True)
    if args.apply:
        if not args.backup:
            parser.error('--apply requires --backup')
        apply_replacements(plan, args.backup.resolve())
        print('Compact source images and legacy URL aliases installed.', flush=True)


if __name__ == '__main__':
    main()
