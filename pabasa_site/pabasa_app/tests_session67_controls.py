from pathlib import Path

from django.test import SimpleTestCase


class Session67ControlsContractTests(SimpleTestCase):
    """Static contracts for the shared Session 6–7 speech surface."""

    root = Path(__file__).resolve().parent

    def test_shared_debug_schema_has_all_required_fields_in_reference_order(self):
        source = (self.root / "templates" / "pabasa_app" / "includes" / "session67_speech_debug_panel.html").read_text(encoding="utf-8")
        fields = [
            "Speech Status", "Expected Text", "Reading Result", "Microphone",
            "Recorder", "VAD State", "Error", "Recent Debug Output",
        ]
        positions = [source.index(field) for field in fields]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("debug-output", source)

    def test_session6_and_session7_controls_use_the_shared_schema_and_layout(self):
        session6 = (self.root / "templates" / "pabasa_app" / "includes" / "session6_prescribed_controls.html").read_text(encoding="utf-8")
        session7 = (self.root / "templates" / "pabasa_app" / "session8_11_prescribed_controls.html").read_text(encoding="utf-8")
        layout = (self.root / "static" / "pabasa_app" / "css" / "session67_reference.css").read_text(encoding="utf-8")
        self.assertIn("session67_speech_debug_panel.html", session6)
        self.assertIn("session67_speech_debug_panel.html", session7)
        self.assertIn("pabasaShowSpeechDebugPanel", (self.root / "static" / "pabasa_app" / "js" / "session6_prescribed_controls.js").read_text(encoding="utf-8"))
        for rule in ("width: min(1250px", "height: 100dvh", "@media (max-width: 680px)"):
            self.assertIn(rule, layout)

    def test_upgraded_lesson16_readers_use_the_shared_capture_binding(self):
        for name in ("prescribed_missing_syllable_page.html", "prescribed_picture_word_matching_page.html"):
            source = (self.root / "templates" / "pabasa_app" / name).read_text(encoding="utf-8")
            self.assertIn("data-basahin-button", source)
            self.assertIn("window.Basahin.bindActivity", source)
            self.assertIn("window.Basahin.capture", source)
