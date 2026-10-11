"""Import section portraits using the existing quality-checked compact WebP encoder."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from pathlib import Path
import re

from PIL import Image
from optimize_static_images import web_image, lossless_webp

REPOSITORY = Path(__file__).resolve().parents[1]
DESTINATION = REPOSITORY / 'pabasa_site/pabasa_app/static/pabasa_app/images/hero'
PREVIEW = REPOSITORY / 'output/sidebar-concepts'


def encode(source):
    if not re.fullmatch(r'[a-z]+', source.stem):
        raise ValueError(f'Unsupported hero filename: {source.name}')
    data = source.read_bytes()
    encoded, quality = web_image(data, 'WEBP', 1024, protected=False)
    if encoded is None:
        encoded = lossless_webp(data)
        quality = {'lossless_quality_fallback': True}
    if not encoded or len(encoded) >= len(data):
        raise ValueError(f'No smaller verified WebP for {source.name}')
    with Image.open(BytesIO(encoded)) as image:
        image.load()
        if image.format != 'WEBP':
            raise ValueError(f'Invalid output for {source.name}')
        dimensions = image.size
    filename = f'{source.stem}bg.webp'
    return source.stem, filename, encoded, {
        'source': source.name, 'asset': filename,
        'original_bytes': len(data), 'compressed_bytes': len(encoded),
        'dimensions': dimensions, 'quality_verification': quality,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    sources = sorted(args.source.glob('*.png'))
    if not sources:
        parser.error('The source directory contains no PNG portraits.')
    # Prepare every asset and check collisions before writing any file.
    with ThreadPoolExecutor(max_workers=4) as pool:
        prepared = list(pool.map(encode, sources))
    preview_assets = PREVIEW / 'assets/hero'
    for _, filename, payload, _ in prepared:
        for directory in (DESTINATION, preview_assets):
            target = directory / filename
            if target.exists() and target.read_bytes() != payload:
                raise ValueError(f'Existing asset differs; preserved: {target}')
    DESTINATION.mkdir(parents=True, exist_ok=True)
    preview_assets.mkdir(parents=True, exist_ok=True)
    for _, filename, payload, _ in prepared:
        for directory in (DESTINATION, preview_assets):
            (directory / filename).write_bytes(payload)
    (DESTINATION / 'manifest.json').write_text(json.dumps({
        name: f'pabasa_app/images/hero/{filename}' for name, filename, _, _ in prepared
    }, indent=2) + '\n', encoding='utf-8')
    rows = [row for _, _, _, row in prepared]
    report = {
        'profile': 'compact WebP using optimize_static_images.web_image',
        'quality_floor_psnr_db': 38, 'assets': rows,
        'original_bytes': sum(row['original_bytes'] for row in rows),
        'compressed_bytes': sum(row['compressed_bytes'] for row in rows),
    }
    report['saved_percent'] = round(100 * (1 - report['compressed_bytes'] / report['original_bytes']), 2)
    (PREVIEW / 'hero-compression-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('original_bytes', 'compressed_bytes', 'saved_percent')}))
    print(f'Imported {len(rows)} verified WebP portraits into application assets and the offline preview.')


if __name__ == '__main__':
    main()
