from pathlib import Path
import shutil
import subprocess

from django.test import SimpleTestCase


class StoryReadingPlayerRuntimeTests(SimpleTestCase):
    def test_basahin_state_persists_across_sentence_advancement_and_skip(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the Story Reading player runtime test")
        app_dir = Path(__file__).resolve().parent
        harness = app_dir / "tests_story_reading_player.js"
        player = app_dir / "static" / "pabasa_app" / "js" / "story_reading_player.js"
        template = app_dir / "templates" / "pabasa_app" / "story_reading_flipbook.html"
        template_source = template.read_text(encoding="utf-8")
        self.assertIn(".subtitle-bubble.is-reading{text-decoration-line:underline", template_source)
        self.assertIn(".story-word{display:inline;margin:0 .08em}", template_source)
        self.assertIn(".story-word.is-current{box-shadow:none}", template_source)
        self.assertIn("@media(max-width:760px)", template_source)
        self.assertIn(".subtitle-bubble{bottom:8px;width:calc(100% - 16px)", template_source)
        for scenario in ("auto", "skip"):
            with self.subTest(scenario=scenario):
                result = subprocess.run(
                    [node, str(harness), str(player), scenario],
                    cwd=app_dir.parents[1],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
                self.assertIn("regression passed", result.stdout)
