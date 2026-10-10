"""Evaluate quality-checked browser variants in an isolated master-image copy."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
import math
from pathlib import Path
import re
import struct

from PIL import Image, ImageChops, ImageOps, ImageStat, features
from PIL.PngImagePlugin import PngInfo


PNG_DATA = re.compile(rb"data:image/png;base64,([A-Za-z0-9+/=\r\n]+)")
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.svg', '.gif', '.webp', '.avif', '.ico'}
GENERATED = re.compile(r'\.(?:png|jpe?g|svg)\.(?:(?:webp|avif)(?:\.svg)?|optimized\.png)$', re.I)
SRGB_CHROMATICITY = (0.3127, 0.329, 0.64, 0.33, 0.3, 0.6, 0.15, 0.06)


def role_limit(path, profile):
    name = path.as_posix().lower()
    if any(word in name for word in ('crla_story_banners/', 'worksheet', 'workbook/', 'trace')):
        return 0, True  # Possible raster text: preserve dimensions and pixels.
    if 'logo' in path.name.lower() or 'favicon' in name:
        return 1024, True
    if 'phrase_reading/' in name and path.suffix.lower() == '.svg':
        return (768 if profile == 'web' else 512), False
    scene_layer = ('/color_mode/' in name and path.stem.lower() in
                   {'sand', 'sea', 'clouds', 'grass', 'pavement', 'vines', 'fence'})
    if scene_layer or any(word in path.stem.lower() for word in ('background', '_bg', '-bg')) or path.name.lower() == 'read.jpg':
        return (2560 if profile == 'web' else 1920), False
    if '/animation/' in name:
        return 768, False
    return (1536 if profile == 'web' else 1024), False


def web_color_is_supported(info):
    if info.get('icc_profile') or 'srgb' in info:
        return True
    gamma = info.get('gamma', 0.45455)
    chromaticity = info.get('chromaticity', SRGB_CHROMATICITY)
    return (abs(gamma - 0.45455) < 0.00002 and len(chromaticity) == 8
            and all(abs(a - b) < 0.00002 for a, b in zip(chromaticity, SRGB_CHROMATICITY)))


def visible_psnr(reference, decoded):
    # Measure visible color on dark and light backgrounds, ignoring hidden RGB.
    errors = []
    for color in ('white', 'black'):
        background = Image.new('RGBA', reference.size, color)
        a = Image.alpha_composite(background, reference).convert('RGB')
        b = Image.alpha_composite(background, decoded).convert('RGB')
        errors.extend(ImageStat.Stat(ImageChops.difference(a, b)).rms)
    mse = sum(error * error for error in errors) / len(errors)
    return 99.0 if mse == 0 else 10 * math.log10(255 * 255 / mse)


def web_image(data, codec, limit, protected=False):
    with Image.open(BytesIO(data)) as source:
        if (getattr(source, 'n_frames', 1) != 1 or source.mode not in {'RGB', 'RGBA', 'P', 'L', 'LA'}
                or not web_color_is_supported(source.info)):
            return None, None
        original_size = source.size
        image = ImageOps.exif_transpose(source).convert('RGBA')
        if limit:
            image.thumbnail((limit, limit), Image.Resampling.LANCZOS)
        transparent = image.getchannel('A').getextrema() != (255, 255)
        # Pillow's AVIF alpha is lossy. Keep transparent assets on exact-alpha WebP.
        if codec == 'AVIF' and (transparent or protected):
            return None, None
        if max(image.size) > 16383:
            return None, None
        metadata = dict(icc_profile=source.info.get('icc_profile', b''), exif=image.info.get('exif', b''))
        qualities = (100,) if protected else ((85, 92, 97) if codec == 'WEBP' else (70, 80, 90))
        for quality in qualities:
            output = BytesIO()
            options = (dict(method=4, alpha_quality=100, lossless=protected, exact=True)
                       if codec == 'WEBP' else dict(speed=6, subsampling='4:4:4', max_threads=1))
            encoded_image = image if transparent else image.convert('RGB')
            encoded_image.save(output, format=codec, quality=quality, **options, **metadata)
            encoded = output.getvalue()
            with Image.open(BytesIO(encoded)) as decoded:
                decoded.load()
                if decoded.size != image.size or decoded.info.get('icc_profile', b'') != metadata['icc_profile']:
                    raise ValueError('Dimensions or color profile verification failed')
                decoded = decoded.convert('RGBA')
                if decoded.getchannel('A').tobytes() != image.getchannel('A').tobytes():
                    raise ValueError('Alpha channel verification failed')
                score = visible_psnr(image, decoded)
                if protected and decoded.tobytes() != image.tobytes():
                    raise ValueError('Protected image pixel verification failed')
            if score >= 38:
                return encoded, dict(source_size=original_size, output_size=image.size,
                                     psnr=round(score, 2), quality=quality, protected=protected)
        # Do not retain an image that fails the quality floor.
        return None, None


def sized_png(data, limit):
    """Keep nonstandard PNG color metadata in PNG rather than guessing sRGB."""
    with Image.open(BytesIO(data)) as source:
        if getattr(source, 'n_frames', 1) != 1 or source.mode not in {'RGB', 'RGBA', 'P', 'L', 'LA'}:
            return None
        image = ImageOps.exif_transpose(source).convert('RGBA')
        if limit:
            image.thumbnail((limit, limit), Image.Resampling.LANCZOS)
        metadata = PngInfo()
        if 'gamma' in source.info:
            metadata.add(b'gAMA', struct.pack('>I', round(source.info['gamma'] * 100000)))
        if 'chromaticity' in source.info:
            metadata.add(b'cHRM', struct.pack('>8I', *(round(v * 100000) for v in source.info['chromaticity'])))
        if 'srgb' in source.info and not source.info.get('icc_profile'):
            metadata.add(b'sRGB', bytes([source.info['srgb']]))
        output = BytesIO()
        image.save(output, format='PNG', optimize=True, pnginfo=metadata,
                   icc_profile=source.info.get('icc_profile'), exif=image.info.get('exif', b''))
        encoded = output.getvalue()
        with Image.open(BytesIO(encoded)) as decoded:
            if decoded.size != image.size or decoded.convert('RGBA').tobytes() != image.tobytes():
                raise ValueError('PNG pixel verification failed')
            for key in ('gamma', 'chromaticity', 'icc_profile'):
                if decoded.info.get(key) != source.info.get(key):
                    raise ValueError('PNG color metadata verification failed')
        return encoded


def lossless_webp(data):
    with Image.open(BytesIO(data)) as image:
        # Do not flatten animations, high-bit-depth images, or reinterpret color.
        if getattr(image, 'n_frames', 1) != 1 or image.mode not in {'RGB', 'RGBA', 'P', 'L', 'LA'}:
            return None
        if max(image.size) > 16383:
            return None
        if not image.info.get('icc_profile') and 'srgb' not in image.info and (
            'gamma' in image.info or 'chromaticity' in image.info
        ):
            return None
        original = image.convert('RGBA')
        output = BytesIO()
        image.save(output, format='WEBP', lossless=True, exact=True, method=4,
                   icc_profile=image.info.get('icc_profile', b''),
                   exif=image.info.get('exif', b''))
        encoded = output.getvalue()
        with Image.open(BytesIO(encoded)) as decoded:
            if decoded.size != original.size or decoded.convert('RGBA').tobytes() != original.tobytes():
                raise ValueError('Lossless pixel verification failed')
            if decoded.info.get('icc_profile', b'') != image.info.get('icc_profile', b''):
                raise ValueError('Color profile verification failed')
        return encoded


def optimize_file(path, profile='lossless'):
    if profile != 'lossless':
        return optimize_web_file(path, profile)
    source = path.read_bytes()
    path.with_name(path.name + ('.avif.svg' if path.suffix.lower() == '.svg' else '.avif')).unlink(missing_ok=True)
    path.with_name(path.name + '.optimized.png').unlink(missing_ok=True)
    if path.suffix.lower() == '.svg':
        def replace(match):
            raster = base64.b64decode(match[1], validate=False)
            encoded = lossless_webp(raster)
            if encoded is None or len(encoded) >= len(raster):
                return match[0]
            return b'data:image/webp;base64,' + base64.b64encode(encoded)
        optimized = PNG_DATA.sub(replace, source)
        destination = path.with_name(path.name + '.webp.svg')
    else:
        optimized = lossless_webp(source)
        destination = path.with_name(path.name + '.webp')
    # Retain only variants with a meaningful benefit. Rebuilding is idempotent.
    if optimized is not None and len(optimized) <= len(source) * 0.95:
        destination.write_bytes(optimized)
        return {'original_bytes': len(source), 'served_bytes': len(optimized), 'optimized': True}
    destination.unlink(missing_ok=True)
    return {'original_bytes': len(source), 'served_bytes': len(source), 'optimized': False}


def optimize_web_file(path, profile):
    source = path.read_bytes()
    limit, protected = role_limit(path, profile)
    results = {}
    for codec in ('WEBP', 'AVIF'):
        stats = []
        if path.suffix.lower() == '.svg':
            def replace(match):
                raster = base64.b64decode(match[1], validate=False)
                with Image.open(BytesIO(raster)) as image:
                    mask = image.mode in {'1', 'L', 'LA'}
                if mask:
                    encoded = lossless_webp(raster) if codec == 'WEBP' else None
                else:
                    encoded, result = web_image(raster, codec, limit, protected)
                    if encoded is None and codec == 'WEBP':
                        encoded, result = web_image(raster, codec, limit, protected=True)
                        if result:
                            result['lossless_quality_fallback'] = True
                    if encoded is None:
                        resized_png = sized_png(raster, limit)
                        if resized_png is not None and len(resized_png) < len(raster):
                            return b'data:image/png;base64,' + base64.b64encode(resized_png)
                    if result:
                        stats.append(result)
                if encoded is None or len(encoded) >= len(raster):
                    return match[0]
                return b'data:image/' + codec.lower().encode() + b';base64,' + base64.b64encode(encoded)
            optimized = PNG_DATA.sub(replace, source)
            destination = path.with_name(path.name + f'.{codec.lower()}.svg')
        else:
            optimized, result = web_image(source, codec, limit, protected)
            if optimized is None and codec == 'WEBP':
                optimized, result = web_image(source, codec, limit, protected=True)
                if result:
                    result['lossless_quality_fallback'] = True
            if result:
                stats.append(result)
            destination = path.with_name(path.name + f'.{codec.lower()}')
        if codec == 'WEBP' and optimized is None and path.suffix.lower() != '.svg':
            optimized = lossless_webp(source)
            stats = [{'lossless_fallback': True}] if optimized else []
        worth_keeping = optimized is not None and len(optimized) <= len(source) * 0.95
        # An AVIF sidecar is useful only when it beats the WebP fallback.
        if codec == 'AVIF' and len(optimized or source) >= results.get('webp', {}).get('bytes', len(source)):
            worth_keeping = False
        if worth_keeping:
            destination.write_bytes(optimized)
            results[codec.lower()] = {'bytes': len(optimized), 'rasters': stats}
        else:
            destination.unlink(missing_ok=True)
    png_destination = path.with_name(path.name + '.optimized.png')
    if path.suffix.lower() == '.png' and not results:
        encoded = sized_png(source, limit)
        if encoded is not None and len(encoded) <= len(source) * 0.95:
            png_destination.write_bytes(encoded)
            results['png'] = {'bytes': len(encoded), 'rasters': [{'png_color_metadata_preserved': True}]}
        else:
            png_destination.unlink(missing_ok=True)
    else:
        png_destination.unlink(missing_ok=True)
    webp_bytes = results.get('webp', {}).get('bytes', results.get('png', {}).get('bytes', len(source)))
    served = results.get('avif', {}).get('bytes', webp_bytes)
    return dict(original_bytes=len(source), served_bytes=served, webp_bytes=webp_bytes,
                optimized=bool(results), variants=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--static-root', type=Path, required=True,
                        help='Isolated evaluation directory containing pabasa_app, never source assets')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--profile', choices=('lossless', 'web', 'compact'), default='compact')
    args = parser.parse_args()
    if not features.check('webp'):
        parser.error('Pillow must have WebP support')
    if args.profile != 'lossless' and not features.check('avif'):
        parser.error('Pillow must have AVIF support for web profiles')
    root = args.static_root.resolve()
    source_root = Path(__file__).resolve().parents[1] / 'pabasa_site/pabasa_app/static'
    if root == source_root or source_root in root.parents or not (root / 'pabasa_app').is_dir():
        parser.error('Use a populated, isolated evaluation directory containing pabasa_app')
    assets = sorted(p for p in (root / 'pabasa_app').rglob('*') if p.is_file()
                    and 'uploads' not in p.relative_to(root).parts
                    and not GENERATED.search(p.name))
    candidates = [p for p in assets if p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.svg'}]
    rows = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        for index, (path, result) in enumerate(zip(candidates, executor.map(
                lambda path: optimize_file(path, args.profile), candidates)), 1):
            rows.append({'path': path.relative_to(root).as_posix(), **result})
            if index % 50 == 0 or index == len(candidates):
                print(f'Checked {index}/{len(candidates)} images', flush=True)
    saved = sum(row['original_bytes'] - row['served_bytes'] for row in rows)
    webp_saved = sum(row['original_bytes'] - row.get('webp_bytes', row['served_bytes']) for row in rows)
    original_images = sum(p.stat().st_size for p in assets if p.suffix.lower() in IMAGE_SUFFIXES)
    original_static = sum(p.stat().st_size for p in assets)
    report = {
        'profile': args.profile,
        'mode': ('lossless, original dimensions, RGBA pixel and ICC profile verified' if args.profile == 'lossless'
                 else 'display sizing; PSNR >= 38 dB at output resolution; exact alpha; protected raster text lossless'),
        'scope': 'pabasa_app static assets excluding uploads; each asset counted once, not page traffic',
        'optimized_count': sum(row['optimized'] for row in rows),
        'original_image_bytes': original_images,
        'webp_capable_image_bytes': original_images - webp_saved,
        'modern_browser_image_bytes': original_images - saved,
        'original_static_bytes': original_static,
        'webp_capable_static_bytes': original_static - webp_saved,
        'modern_browser_static_bytes': original_static - saved,
        'saved_bytes': saved,
        'images': rows,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'images'}, indent=2))


if __name__ == '__main__':
    main()
