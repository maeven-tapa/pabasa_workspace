"""Serve quality-checked browser variants without changing existing asset URLs."""
from django.utils.cache import patch_vary_headers
from whitenoise.middleware import WhiteNoiseMiddleware

from .static_assets import canonical_asset_name


def accepted_quality(header, desired_type):
    # Wildcards do not prove WebP support; respect an explicit q=0 opt-out.
    for entry in header.lower().split(','):
        media_type, *parameters = entry.strip().split(';')
        if media_type.strip() != desired_type:
            continue
        quality = 1.0
        for parameter in parameters:
            name, separator, value = parameter.strip().partition('=')
            if separator and name.strip() == 'q':
                try:
                    quality = float(value.strip())
                except ValueError:
                    return 0
        return quality if 0 < quality <= 1 else 0
    return 0


def accepts_webp(header):
    return accepted_quality(header, 'image/webp') > 0


class OptimizedImageMiddleware(WhiteNoiseMiddleware):
    def __call__(self, request):
        path = request.path_info
        if path.startswith(self.static_prefix):
            name = path[len(self.static_prefix):]
            canonical = canonical_asset_name(name)
            if canonical != name:
                lookup = self.find_file if self.autorefresh else self.files.get
                compact = lookup(self.static_prefix + canonical)
                if compact is not None:
                    return self.serve(compact, request)
        prefix = self.static_prefix + 'pabasa_app/'
        suffix = path.rsplit('.', 1)[-1].lower()
        eligible = (path.startswith(prefix) and '/uploads/' not in path
                    and suffix in {'png', 'jpg', 'jpeg', 'svg'}
                    and not path.endswith(('.webp.svg', '.avif.svg', '.optimized.png')))
        if not eligible:
            return super().__call__(request)
        lookup = self.find_file if self.autorefresh else self.files.get
        original = lookup(path)
        if original is None:
            return super().__call__(request)
        png_fallback = lookup(path + '.optimized.png') if suffix == 'png' else None
        if png_fallback is not None:
            original = png_fallback
        variants = {codec: lookup(path + f'.{codec}' + ('.svg' if suffix == 'svg' else ''))
                    for codec in ('webp', 'avif')}
        if not any(variants.values()):
            return self.serve(original, request)
        accept = request.headers.get('Accept', '')
        choices = [(accepted_quality(accept, f'image/{codec}'), codec == 'avif', variant)
                   for codec, variant in variants.items() if variant is not None
                   and accepted_quality(accept, f'image/{codec}') > 0]
        selected = max(choices, key=lambda choice: choice[:2])[2] if choices else original
        response = self.serve(selected, request)
        # Both responses (including HEAD/304) must vary to prevent cache mixups.
        patch_vary_headers(response, ['Accept'])
        return response
