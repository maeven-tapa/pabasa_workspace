import base64
from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from PIL import Image

from .static_images import OptimizedImageMiddleware
from .static_assets import CompactStaticFilesStorage, canonical_asset_name, image_asset_aliases


spec = spec_from_file_location('static_image_optimizer',
                              Path(__file__).resolve().parents[2] / 'tools/optimize_static_images.py')
optimizer = module_from_spec(spec)
spec.loader.exec_module(optimizer)


class StaticImageTests(SimpleTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        assets = self.root / 'pabasa_app/images'
        assets.mkdir(parents=True)
        self.original = assets / 'test.png'
        image = Image.new('RGBA', (128, 128), (12, 34, 56, 0))
        image.putpixel((0, 0), (150, 100, 200, 128))
        image.save(self.original)
        optimizer.optimize_file(self.original)
        self.assertTrue(self.original.with_name('test.png.webp').exists())
        self.url = '/static/pabasa_app/images/test.png'
        self.factory = RequestFactory()

    def middleware(self, autorefresh=False):
        with override_settings(STATIC_ROOT=self.root, STATIC_URL='/static/',
                               WHITENOISE_AUTOREFRESH=autorefresh, WHITENOISE_USE_FINDERS=False):
            return OptimizedImageMiddleware(lambda request: HttpResponse('application', status=404))

    def consume(self, response):
        try:
            return b''.join(response.streaming_content)
        finally:
            response.close()

    def test_lossless_pixel_dimensions_and_transparency(self):
        response = self.middleware()(self.factory.get(self.url, HTTP_ACCEPT='image/avif,image/webp,*/*'))
        self.assertEqual(response['Content-Type'], 'image/webp')
        with Image.open(BytesIO(self.consume(response))) as decoded, Image.open(self.original) as original:
            self.assertEqual(decoded.size, original.size)
            self.assertEqual(decoded.convert('RGBA').tobytes(), original.convert('RGBA').tobytes())

    def test_clients_without_explicit_support_get_original(self):
        for accept in ('', '*/*', 'image/png', 'image/webp;q=0', 'image/webp;q=invalid'):
            with self.subTest(accept=accept):
                response = self.middleware()(self.factory.get(self.url, HTTP_ACCEPT=accept))
                self.assertEqual(response['Content-Type'], 'image/png')
                self.assertIn('Accept', response['Vary'])
                self.assertEqual(self.consume(response), self.original.read_bytes())

    def test_conditional_requests_do_not_mix_representations(self):
        middleware = self.middleware()
        webp = middleware(self.factory.get(self.url, HTTP_ACCEPT='image/webp'))
        etag = webp['ETag']
        self.consume(webp)
        cached = middleware(self.factory.get(self.url, HTTP_ACCEPT='image/webp', HTTP_IF_NONE_MATCH=etag))
        self.assertEqual(cached.status_code, 304)
        self.assertIn('Accept', cached['Vary'])
        cached.close()
        fallback = middleware(self.factory.get(self.url, HTTP_ACCEPT='image/png', HTTP_IF_NONE_MATCH=etag))
        self.assertEqual(fallback.status_code, 200)
        self.assertEqual(self.consume(fallback), self.original.read_bytes())

    def test_head_has_selected_length_without_body(self):
        response = self.middleware()(self.factory.head(self.url, HTTP_ACCEPT='image/webp'))
        self.assertEqual(response['Content-Type'], 'image/webp')
        self.assertEqual(int(response['Content-Length']), self.original.with_name('test.png.webp').stat().st_size)
        self.assertEqual(self.consume(response), b'')

    def test_missing_variant_uses_original_and_autorefresh_finds_variants(self):
        middleware = self.middleware(autorefresh=True)
        response = middleware(self.factory.get(self.url, HTTP_ACCEPT='image/webp'))
        self.assertEqual(response['Content-Type'], 'image/webp')
        self.consume(response)
        self.original.with_name('test.png.webp').unlink()
        response = middleware(self.factory.get(self.url, HTTP_ACCEPT='image/webp'))
        self.assertEqual(response['Content-Type'], 'image/png')
        self.consume(response)

    def test_uploads_and_application_routes_are_excluded(self):
        uploads = self.root / 'pabasa_app/uploads'
        uploads.mkdir()
        (uploads / 'test.png').write_bytes(self.original.read_bytes())
        (uploads / 'test.png.webp').write_bytes(self.original.with_name('test.png.webp').read_bytes())
        middleware = self.middleware()
        response = middleware(self.factory.get('/static/pabasa_app/uploads/test.png', HTTP_ACCEPT='image/webp'))
        self.assertEqual(response['Content-Type'], 'image/png')
        self.consume(response)
        self.assertEqual(middleware(self.factory.get('/dashboard/', HTTP_ACCEPT='image/webp')).status_code, 404)

    def test_svg_embedded_images_are_lossless_and_vector_markup_is_retained(self):
        path = self.original.with_name('test.svg')
        uri = b'data:image/png;base64,' + base64.b64encode(self.original.read_bytes())
        source = b'<svg xmlns="http://www.w3.org/2000/svg"><image href="' + uri + b'"/><path d="M0 0L5 5"/></svg>'
        path.write_bytes(source)
        result = optimizer.optimize_file(path)
        self.assertTrue(result['optimized'])
        variant = path.with_name('test.svg.webp.svg').read_bytes()
        self.assertIn(b'<path d="M0 0L5 5"/>', variant)
        self.assertIn(b'data:image/webp;base64,', variant)
        response = self.middleware()(self.factory.get(self.url.replace('.png', '.svg'), HTTP_ACCEPT='image/webp'))
        self.assertEqual(response['Content-Type'], 'image/svg+xml')
        self.assertEqual(self.consume(response), variant)

    def test_animation_is_not_flattened(self):
        stream = BytesIO()
        Image.new('RGBA', (32, 32), 'red').save(
            stream, format='PNG', save_all=True, append_images=[Image.new('RGBA', (32, 32), 'blue')], duration=50)
        self.assertIsNone(optimizer.lossless_webp(stream.getvalue()))

    def test_color_profile_is_preserved_and_unsupported_color_metadata_is_skipped(self):
        stream = BytesIO()
        profile = b'profile-bytes-for-roundtrip-test'
        Image.new('RGB', (64, 64), 'red').save(stream, format='PNG', icc_profile=profile)
        encoded = optimizer.lossless_webp(stream.getvalue())
        with Image.open(BytesIO(encoded)) as decoded:
            self.assertEqual(decoded.info['icc_profile'], profile)
        from PIL.PngImagePlugin import PngInfo
        import struct
        metadata = PngInfo()
        metadata.add(b'gAMA', struct.pack('>I', 100000))
        stream = BytesIO()
        Image.new('RGB', (64, 64), 'red').save(stream, format='PNG', pnginfo=metadata)
        self.assertIsNone(optimizer.lossless_webp(stream.getvalue()))

    def test_web_profile_sizes_art_and_preserves_alpha(self):
        image = Image.new('RGBA', (2100, 1600), (20, 150, 240, 0))
        image.paste((180, 60, 20, 128), (200, 200, 1600, 1300))
        stream = BytesIO()
        image.save(stream, format='PNG')
        encoded, stats = optimizer.web_image(stream.getvalue(), 'WEBP', 1024)
        self.assertIsNotNone(encoded)
        self.assertLessEqual(max(stats['output_size']), 1024)
        self.assertGreaterEqual(stats['psnr'], 38)
        resized = image.copy()
        resized.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        with Image.open(BytesIO(encoded)) as decoded:
            self.assertEqual(decoded.convert('RGBA').getchannel('A').tobytes(), resized.getchannel('A').tobytes())
        self.assertEqual(optimizer.web_image(stream.getvalue(), 'AVIF', 1024), (None, None))

    def test_raster_text_is_not_resized_or_lossily_encoded(self):
        from PIL import ImageDraw
        path = self.original.with_name('worksheet.png')
        image = Image.new('RGB', (1800, 1400), 'white')
        ImageDraw.Draw(image).text((100, 100), 'Read this sentence clearly.', fill='black', font_size=40)
        image.save(path)
        optimizer.optimize_file(path, 'compact')
        with Image.open(path.with_name('worksheet.png.webp')) as decoded:
            self.assertEqual(decoded.size, image.size)
            self.assertEqual(decoded.convert('RGB').tobytes(), image.tobytes())

    def test_avif_negotiation_and_quality_preference(self):
        avif = self.original.with_name('test.png.avif')
        Image.new('RGB', (128, 128), 'blue').save(avif, format='AVIF')
        middleware = self.middleware()
        for accept, expected in [('image/avif,image/webp', 'image/avif'),
                                 ('image/avif;q=0,image/webp', 'image/webp'),
                                 ('image/avif;q=0.5,image/webp;q=0.9', 'image/webp'),
                                 ('image/avif;q=invalid', 'image/png')]:
            with self.subTest(accept=accept):
                response = middleware(self.factory.get(self.url, HTTP_ACCEPT=accept))
                self.assertEqual(response['Content-Type'], expected)
                self.assertIn('Accept', response['Vary'])
                self.consume(response)

    def test_scene_layers_have_larger_resolution_budget_than_small_objects(self):
        self.assertEqual(optimizer.role_limit(Path('pabasa_app/color_mode/beach/sea.png'), 'web'), (2560, False))
        self.assertEqual(optimizer.role_limit(Path('pabasa_app/color_mode/zoo/vines.png'), 'compact'), (1920, False))
        self.assertEqual(optimizer.role_limit(Path('pabasa_app/color_mode/farm/sheep.png'), 'compact'), (1024, False))

    def test_nonstandard_color_png_is_sized_without_reinterpreting_color(self):
        from PIL.PngImagePlugin import PngInfo
        import struct
        path = self.original.with_name('linear-color.png')
        image = Image.new('RGB', (2000, 1000), (40, 150, 80))
        metadata = PngInfo()
        metadata.add(b'gAMA', struct.pack('>I', 100000))
        image.save(path, pnginfo=metadata, compress_level=0)
        result = optimizer.optimize_file(path, 'compact')
        self.assertIn('png', result['variants'])
        png = path.with_name('linear-color.png.optimized.png')
        with Image.open(png) as decoded:
            self.assertEqual(decoded.info['gamma'], 1.0)
            self.assertEqual(decoded.size, (1024, 512))
            self.assertEqual(decoded.convert('RGB').getpixel((100, 100)), (40, 150, 80))
        response = self.middleware()(self.factory.get(self.url.replace('test.png', 'linear-color.png'), HTTP_ACCEPT='image/webp'))
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertEqual(self.consume(response), png.read_bytes())


class CompactSourceAssetTests(SimpleTestCase):
    def test_every_legacy_alias_has_one_real_compact_source(self):
        root = Path(__file__).resolve().parent / 'static'
        aliases = image_asset_aliases()
        self.assertTrue(aliases)
        self.assertEqual(len(set(aliases.values())), len(aliases))
        for old, new in aliases.items():
            with self.subTest(asset=old):
                self.assertNotIn('uploads', Path(old).parts)
                self.assertFalse((root / old).exists())
                self.assertTrue((root / new).is_file())

    def test_static_storage_outputs_canonical_urls_and_keeps_uploads(self):
        storage = CompactStaticFilesStorage(base_url='/static/')
        old = 'pabasa_app/color_mode/farm/sheep.png'
        self.assertEqual(storage.url(old), '/static/pabasa_app/color_mode/farm/sheep.webp')
        self.assertEqual(storage.url('pabasa_app/uploads/a.png'), '/static/pabasa_app/uploads/a.png')
        self.assertEqual(canonical_asset_name('unrelated/a.png'), 'unrelated/a.png')

    def test_legacy_urls_serve_correct_mime_in_production_and_development(self):
        from django.contrib.staticfiles.views import serve
        factory = RequestFactory()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            asset = root / 'pabasa_app/color_mode/farm/sheep.webp'
            asset.parent.mkdir(parents=True)
            Image.new('RGB', (64, 64), 'blue').save(asset)
            with override_settings(STATIC_ROOT=root, STATIC_URL='/static/',
                                   WHITENOISE_AUTOREFRESH=False, WHITENOISE_USE_FINDERS=False):
                middleware = OptimizedImageMiddleware(lambda request: HttpResponse(status=404))
            response = middleware(factory.get('/static/pabasa_app/color_mode/farm/sheep.png'))
            self.assertEqual(response['Content-Type'], 'image/webp')
            self.assertEqual(b''.join(response.streaming_content), asset.read_bytes())
            response.close()
        with override_settings(DEBUG=True):
            response = serve(factory.get('/static/pabasa_app/color_mode/farm/sheep.png'),
                             'pabasa_app/color_mode/farm/sheep.png')
            self.assertEqual(response['Content-Type'], 'image/webp')
            with Image.open(BytesIO(b''.join(response.streaming_content))) as image:
                self.assertEqual(image.size, (1024, 1024))
            response.close()

    def test_homepage_discovers_compact_mascot_frames(self):
        from .views import home
        with patch('pabasa_app.views.render') as render:
            home(RequestFactory().get('/'))
        frames = render.call_args.args[2]['reading_animation_frames']
        root = Path(__file__).resolve().parent / 'static'
        self.assertEqual(len(frames), len(list((root / 'pabasa_app/animation/Reading').iterdir())))
        self.assertGreater(len(frames), 0)
        self.assertTrue(all(frame.endswith(('.webp', '.avif', '.png')) and (root / frame).is_file()
                            for frame in frames))

    def test_picture_word_catalog_keeps_legacy_saved_filenames(self):
        from .views import _picture_word_catalog, _find_picture_word_catalog_item
        from .static_assets import original_asset_name
        catalog = _picture_word_catalog()
        item = next(item for item in catalog['customItems'] if item['image'].endswith('.avif'))
        from urllib.parse import unquote
        legacy_name = Path(original_asset_name(unquote(item['image_path']).removeprefix('/static/'))).name
        found = _find_picture_word_catalog_item(catalog, filename=legacy_name, source_type='custom')
        self.assertEqual(found, item)
        unrelated = str(Path(legacy_name).with_suffix('.gif'))
        self.assertIsNone(_find_picture_word_catalog_item(catalog, filename=unrelated, source_type='custom'))

    def test_report_logo_and_email_logo_remain_usable(self):
        from reportlab.lib.utils import ImageReader
        from .views import _principal_report_logo_path
        from .email_branding import email_logo_url
        self.assertEqual(ImageReader(str(_principal_report_logo_path({}))).getSize(), (1024, 1024))
        self.assertTrue(email_logo_url().endswith('/pabasa_app/images/pabasa_logo.png'))


@override_settings(DEBUG=False, STATIC_ROOT=None, WHITENOISE_USE_FINDERS=True,
                   WHITENOISE_AUTOREFRESH=False)
class DirectStaticServingTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.middleware = OptimizedImageMiddleware(lambda request: HttpResponse('application', status=404))

    def request(self, path, method='get', **headers):
        return self.middleware(getattr(RequestFactory(), method)(path, **headers))

    def consume(self, response):
        try:
            return b''.join(response.streaming_content)
        finally:
            response.close()

    def test_all_images_and_legacy_aliases_work_without_collected_directory(self):
        root = Path(__file__).resolve().parent / 'static'
        original_names = {new: old for old, new in image_asset_aliases().items()}
        suffixes = optimizer.IMAGE_SUFFIXES
        from urllib.parse import quote
        for asset in root.rglob('*'):
            if not asset.is_file() or 'uploads' in asset.relative_to(root).parts or asset.suffix.lower() not in suffixes:
                continue
            name = asset.relative_to(root).as_posix()
            with self.subTest(asset=name):
                response = self.request('/static/' + quote(original_names.get(name, name)))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.consume(response), asset.read_bytes())

    def test_package_admin_assets_are_served_alongside_app_assets(self):
        for path, content_type in (('/static/admin/css/base.css', 'text/css'),
                                   ('/static/admin/js/core.js', 'text/javascript')):
            with self.subTest(asset=path):
                response = self.request(path)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response['Content-Type'].startswith(content_type))
                self.assertGreater(len(self.consume(response)), 0)

    def test_direct_images_keep_head_range_and_conditional_caching(self):
        path = '/static/pabasa_app/images/teacher_bg.jpg'
        response = self.request(path)
        self.assertEqual(response['Content-Type'], 'image/avif')
        etag = response['ETag']
        length = int(response['Content-Length'])
        body = self.consume(response)
        cached = self.request(path, HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(cached.status_code, 304)
        cached.close()
        head = self.request(path, method='head')
        self.assertEqual(int(head['Content-Length']), length)
        self.assertEqual(self.consume(head), b'')
        partial = self.request(path, HTTP_RANGE='bytes=0-99')
        self.assertEqual(partial.status_code, 206)
        self.assertEqual(self.consume(partial), body[:100])

    def test_production_requests_use_the_startup_index(self):
        with patch.object(self.middleware, 'find_file', side_effect=AssertionError('Unexpected source lookup')):
            for path in ('/static/pabasa_app/color_mode/farm/sheep.webp',
                         '/static/pabasa_app/color_mode/farm/sheep.png',
                         '/static/admin/css/base.css'):
                response = self.request(path)
                self.assertEqual(response.status_code, 200)
                self.consume(response)

    def test_missing_assets_and_application_routes_keep_application_response(self):
        for path in ('/static/pabasa_app/images/missing.webp', '/assessment/'):
            response = self.request(path)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.content, b'application')
