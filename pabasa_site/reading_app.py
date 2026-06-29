"""
PABASA - STT Test - A PySide6 application for speech-guided reading checks.
Highlights words sequentially with smooth animation and visual feedback.
It can also capture spoken sentences with Google Cloud Speech-to-Text.
"""

import base64
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
import wave
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

def record_microphone_audio(duration: float = 5.0) -> str:
    """Record microphone audio into a temporary WAV file."""
    try:
        import pyaudio
    except ImportError as exc:
        raise RuntimeError("Install pyaudio with: pip install pyaudio") from exc

    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=2048,
    )

    frames = []
    total_chunks = int(16000 / 2048 * duration)
    try:
        for _ in range(total_chunks):
            data = stream.read(2048, exception_on_overflow=False)
            frames.append(data)
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()

    tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_file.close()

    with wave.open(tmp_file.name, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"".join(frames))

    return tmp_file.name


def transcribe_audio_file(
    audio_path: str,
    api_key: str,
    language_code: str = "en-US",
    phrase_hints: list[str] | None = None,
    model: str = "latest_short",
    project_id: str = "",
    location: str = "us",
) -> str:
    """Send recorded audio to Google Cloud Speech-to-Text using an API key."""
    if model == "chirp_3":
        try:
            return transcribe_audio_file_v2_chirp3(audio_path, api_key, language_code, project_id, location)
        except RuntimeError as exc:
            if is_chirp3_access_error(str(exc)):
                fallback_model = "latest_short" if language_code == "en-US" else ""
                return transcribe_audio_file_v1(audio_path, api_key, language_code, phrase_hints, fallback_model)
            raise

    return transcribe_audio_file_v1(audio_path, api_key, language_code, phrase_hints, model)


def transcribe_audio_file_v1(
    audio_path: str,
    api_key: str,
    language_code: str,
    phrase_hints: list[str] | None,
    model: str,
) -> str:
    """Send recorded audio to Google Cloud Speech-to-Text V1."""

    with open(audio_path, "rb") as audio_file:
        audio_bytes = audio_file.read()

    config = {
        "encoding": "LINEAR16",
        "sampleRateHertz": 16000,
        "languageCode": language_code,
        "enableAutomaticPunctuation": language_code == "en-US",
        "maxAlternatives": 3,
    }
    if model:
        config["model"] = model
    if phrase_hints:
        config["speechContexts"] = [{"phrases": phrase_hints, "boost": 20.0}]

    payload = {
        "config": config,
        "audio": {"content": base64.b64encode(audio_bytes).decode("utf-8")},
    }

    request = urllib.request.Request(
        f"https://speech.googleapis.com/v1p1beta1/speech:recognize?key={api_key}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        try:
            error_message = json.loads(details).get("error", {}).get("message", details)
        except json.JSONDecodeError:
            error_message = details or exc.reason
        raise RuntimeError(f"Google STT HTTP {exc.code}: {error_message}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error while contacting Google STT: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Google STT returned an invalid response.") from exc

    if not result.get("results"):
        return ""

    alternatives = result["results"][0].get("alternatives", [])
    if not alternatives:
        return ""

    transcript = alternatives[0].get("transcript", "")
    return transcript.strip()


def transcribe_audio_file_v2_chirp3(
    audio_path: str,
    api_key: str,
    language_code: str,
    project_id: str,
    location: str,
) -> str:
    """Send recorded audio to Google Cloud Speech-to-Text V2 Chirp 3."""
    if not project_id:
        raise RuntimeError("Set GOOGLE_CLOUD_PROJECT to use Chirp 3 for Marungko mode.")

    with open(audio_path, "rb") as audio_file:
        audio_bytes = audio_file.read()

    payload = {
        "config": {
            "autoDecodingConfig": {},
            "languageCodes": [language_code],
            "model": "chirp_3",
            "features": {"enableAutomaticPunctuation": False},
        },
        "content": base64.b64encode(audio_bytes).decode("utf-8"),
    }

    request = urllib.request.Request(
        f"https://speech.googleapis.com/v2/projects/{project_id}/locations/{location}/recognizers/_:recognize?key={api_key}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        try:
            error_message = json.loads(details).get("error", {}).get("message", details)
        except json.JSONDecodeError:
            error_message = details or exc.reason
        raise RuntimeError(f"Google STT V2 Chirp 3 HTTP {exc.code}: {error_message}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error while contacting Google STT V2 Chirp 3: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Google STT V2 Chirp 3 returned an invalid response.") from exc

    if not result.get("results"):
        return ""

    alternatives = result["results"][0].get("alternatives", [])
    if not alternatives:
        return ""

    return alternatives[0].get("transcript", "").strip()


def is_chirp3_access_error(message: str) -> bool:
    """Return whether Chirp 3 failed because API-key auth lacks V2 recognizer access."""
    lowered = message.lower()
    return (
        "permission" in lowered
        or "denied" in lowered
        or "may not exist" in lowered
        or "troubleshooter" in lowered
    )

class SpeechWorker(QObject):
    """Runs repeated microphone capture and transcription away from the UI thread."""

    transcript_ready = Signal(str)
    finished = Signal()
    error = Signal(str)
    status = Signal(str)

    def __init__(
        self,
        api_key: str,
        language_code: str = "en-US",
        phrase_hints: list[str] | None = None,
        model: str = "latest_short",
        project_id: str = "",
        location: str = "us",
        duration: float = 3.0,
    ):
        super().__init__()
        self.api_key = api_key
        self.language_code = language_code
        self.phrase_hints = phrase_hints or []
        self.model = model
        self.project_id = project_id
        self.location = location
        self.duration = duration
        self.keep_listening = True
        self.transcription_failures = 0

    def run(self):
        try:
            while self.keep_listening:
                audio_path = None
                try:
                    self.status.emit("Listening...")
                    audio_path = record_microphone_audio(duration=self.duration)
                    if not self.keep_listening:
                        break

                    self.status.emit("Checking your words...")
                    try:
                        transcript = transcribe_audio_file(
                            audio_path,
                            self.api_key,
                            self.language_code,
                            self.phrase_hints,
                            self.model,
                            self.project_id,
                            self.location,
                        )
                    except RuntimeError as exc:
                        self.transcription_failures += 1
                        if self.transcription_failures >= 3:
                            raise
                        self.status.emit(f"Transcript error, listening again... ({exc})")
                        continue

                    self.transcription_failures = 0
                    if transcript:
                        self.transcript_ready.emit(transcript)
                    else:
                        self.status.emit("No speech detected. Keep reading.")
                finally:
                    if audio_path and os.path.exists(audio_path):
                        os.remove(audio_path)
        except Exception as exc:  # pragma: no cover - UI-facing fallback
            self.error.emit(str(exc))
        finally:
            self.finished.emit()

    def stop(self):
        self.keep_listening = False


class WordFlowReader(QMainWindow):
    """Main application window for PABASA - STT Test."""

    GOOGLE_API_KEY = "AIzaSyD1NqLTpMSzmkAdFX6UpcuJ-y4bT9mrXbk"
    GOOGLE_CLOUD_PROJECT_ID = "direct-outlet-499701-p6"
    GOOGLE_CHIRP_LOCATION = "global"
    VOWELS = set("aeiou")
    SPOKEN_VOWELS = {
        "a": "a",
        "ah": "a",
        "ay": "a",
        "aye": "a",
        "e": "e",
        "eh": "e",
        "ee": "e",
        "i": "i",
        "eye": "i",
        "o": "o",
        "oh": "o",
        "owe": "o",
        "u": "u",
        "uh": "u",
        "oo": "u",
        "you": "u",
    }
    VOWEL_SOUND_ALIASES = {
        "a": {"a", "ah"},
        "e": {"e", "eh"},
        "i": {"i", "e", "ee", "y"},
        "o": {"o", "oh", "ow"},
        "u": {"u", "oo", "ew"},
    }

    SAMPLE_SENTENCES = [
        "The quick brown fox jumps over the lazy dog.",
        "Python is a powerful and elegant programming language.",
        "Reading with focus improves comprehension and retention.",
        "Technology makes learning more interactive and engaging.",
        "Practice consistent reading habits for better literacy skills.",
        "Animated word-by-word reading enhances visual processing.",
        "Every word has meaning and contributes to understanding.",
        "Smooth animations make the reading experience enjoyable.",
    ]
    MARUNGKO_MATERIALS = [
        "ma me mi mo mu",
        "sa se si so su",
        "ma sa masa",
        "mama mimi masa",
        "ba be bi bo bu",
        "ta te ti to tu",
        "ka ke ki ko ku",
        "la le li lo lu",
        "na ne ni no nu",
        "ga ge gi go gu",
        "ra re ri ro ru",
        "pa pe pi po pu",
        "ma ba ta ka la",
        "mama basa bata",
    ]
    MARUNGKO_PHRASE_HINTS = [
        "ma",
        "me",
        "mi",
        "mo",
        "mu",
        "sa",
        "se",
        "si",
        "so",
        "su",
        "ba",
        "be",
        "bi",
        "bo",
        "bu",
        "ta",
        "te",
        "ti",
        "to",
        "tu",
        "ka",
        "ke",
        "ki",
        "ko",
        "ku",
        "la",
        "le",
        "li",
        "lo",
        "lu",
        "na",
        "ne",
        "ni",
        "no",
        "nu",
        "mama",
        "basa",
        "bata",
        "masa",
        "mimi",
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PABASA - STT Test")
        self.setGeometry(100, 100, 980, 720)
        self.setMinimumSize(820, 620)
        self.setStyleSheet("background-color: #eef3f8;")

        self.active_mode = "sentence"
        self.sentences = self.SAMPLE_SENTENCES.copy()
        self.current_sentence_index = 0
        self.current_word_index = 0
        self.current_syllable_index = 0
        self.is_speech_active = False
        self.words = []
        self.syllables = []
        self.word_syllable_ranges = []
        self.speech_thread = None
        self.speech_worker = None

        self.setup_ui()
        self.load_sentence()

    def setup_ui(self):
        """Initialize the user interface."""
        central_widget = QWidget()
        central_widget.setStyleSheet(
            """
            QWidget {
                color: #172033;
                font-family: 'Segoe UI';
            }
            """
        )
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(14)

        title_label = QLabel("PABASA - STT Test")
        title_font = QFont("Segoe UI", 26, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #14213d; margin-bottom: 4px;")
        main_layout.addWidget(title_label)

        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(8)
        self.sentence_mode_button = self.create_mode_button("Sentence", "sentence")
        self.marungko_mode_button = self.create_mode_button("Marungko", "marungko")
        mode_layout.addStretch()
        mode_layout.addWidget(self.sentence_mode_button)
        mode_layout.addWidget(self.marungko_mode_button)
        mode_layout.addStretch()
        main_layout.addLayout(mode_layout)
        self.update_mode_buttons()

        self.stt_config_label = QLabel()
        self.stt_config_label.setAlignment(Qt.AlignCenter)
        self.stt_config_label.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        self.stt_config_label.setStyleSheet(
            """
            QLabel {
                color: #486581;
                background-color: #e8f1fb;
                border: 1px solid #cfe0f2;
                border-radius: 8px;
                padding: 6px 10px;
            }
            """
        )
        main_layout.addWidget(self.stt_config_label)
        self.update_stt_config_label()

        sentence_frame = QFrame()
        sentence_frame.setStyleSheet(
            """
            QFrame {
                background-color: #ffffff;
                border: 1px solid #d9e2ec;
                border-radius: 8px;
                padding: 18px;
            }
            """
        )
        sentence_layout = QVBoxLayout()

        self.sentence_display = QTextEdit()
        self.sentence_display.setReadOnly(True)
        self.sentence_display.setStyleSheet(
            """
            QTextEdit {
                background-color: #fbfcfe;
                border: none;
                font-size: 20px;
                font-family: 'Segoe UI';
                padding: 18px;
                border-radius: 6px;
            }
            """
        )
        self.sentence_display.setMinimumHeight(150)
        self.sentence_display.setAlignment(Qt.AlignCenter)
        sentence_layout.addWidget(self.sentence_display)

        sentence_frame.setLayout(sentence_layout)
        main_layout.addWidget(sentence_frame)

        raw_frame = QFrame()
        raw_frame.setStyleSheet(
            """
            QFrame {
                background-color: #ffffff;
                border: 1px solid #d9e2ec;
                border-radius: 8px;
                padding: 12px;
            }
            """
        )
        raw_layout = QVBoxLayout()

        raw_title = QLabel("Raw microphone words")
        raw_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        raw_title.setStyleSheet("color: #334e68;")
        raw_layout.addWidget(raw_title)

        self.raw_transcript_display = QTextEdit()
        self.raw_transcript_display.setReadOnly(True)
        self.raw_transcript_display.setPlaceholderText("Speech recognized by Google will appear here.")
        self.raw_transcript_display.setMinimumHeight(90)
        self.raw_transcript_display.setStyleSheet(
            """
            QTextEdit {
                background-color: #f8fafc;
                border: 1px solid #edf2f7;
                font-size: 14px;
                font-family: 'Segoe UI';
                padding: 10px;
                border-radius: 6px;
            }
            """
        )
        raw_layout.addWidget(self.raw_transcript_display)
        raw_frame.setLayout(raw_layout)
        main_layout.addWidget(raw_frame)

        self.status_label = QLabel("Ready to start reading")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        self.status_label.setStyleSheet("color: #486581; padding: 4px;")
        main_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                background-color: #dde7f0;
                border: none;
                border-radius: 6px;
                text-align: center;
                height: 18px;
                color: #243b53;
                font-weight: 600;
            }
            QProgressBar::chunk {
                background-color: #2f9e44;
                border-radius: 6px;
            }
            """
        )
        self.progress_bar.setMinimum(0)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        speech_title = QLabel("Google Cloud Speech-to-Text")
        speech_title.setAlignment(Qt.AlignCenter)
        speech_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        speech_title.setStyleSheet("color: #1f6feb; margin-top: 4px;")
        main_layout.addWidget(speech_title)

        speech_helper = QLabel(
            "Click Speak and read the text on screen. Correct words will highlight as you say them."
        )
        speech_helper.setAlignment(Qt.AlignCenter)
        speech_helper.setWordWrap(True)
        speech_helper.setStyleSheet("color: #627d98;")
        main_layout.addWidget(speech_helper)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.speech_button = self.create_button("🎤 Speak", self.transcribe_speech, "#4285F4")
        self.speech_button.setMinimumWidth(180)
        self.reset_button = self.create_button("↻ Reset", self.reset_reading, "#2196F3")
        self.next_button = self.create_button("→ Next Sentence", self.next_sentence, "#9C27B0")

        button_layout.addStretch()
        button_layout.addWidget(self.speech_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addWidget(self.next_button)
        button_layout.addStretch()

        main_layout.addLayout(button_layout)

        self.counter_label = QLabel()
        self.counter_label.setAlignment(Qt.AlignCenter)
        self.counter_label.setFont(QFont("Segoe UI", 9))
        self.counter_label.setStyleSheet("color: #999999;")
        main_layout.addWidget(self.counter_label)

        main_layout.addStretch()
        central_widget.setLayout(main_layout)

    def create_button(self, text: str, callback, color: str) -> QPushButton:
        """Create a styled button."""
        button = QPushButton(text)
        button.setFont(QFont("Segoe UI", 10, QFont.Bold))
        button.setMinimumHeight(40)
        button.setMinimumWidth(120)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(callback)
        button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 9px 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self.darken_color(color)};
            }}
            QPushButton:pressed {{
                background-color: {self.darken_color(color, 0.8)};
            }}
            QPushButton:disabled {{
                background-color: #cbd5e1;
                color: #64748b;
            }}
            """
        )
        return button

    def create_mode_button(self, text: str, mode: str) -> QPushButton:
        """Create a segmented mode button."""
        button = QPushButton(text)
        button.setCheckable(True)
        button.setMinimumHeight(34)
        button.setMinimumWidth(120)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(lambda: self.switch_mode(mode))
        button.setStyleSheet(
            """
            QPushButton {
                background-color: #ffffff;
                color: #486581;
                border: 1px solid #bcccdc;
                border-radius: 8px;
                padding: 7px 14px;
                font-weight: 700;
            }
            QPushButton:hover {
                border-color: #1f6feb;
                color: #1f6feb;
            }
            QPushButton:checked {
                background-color: #1f6feb;
                color: white;
                border-color: #1f6feb;
            }
            """
        )
        return button

    def switch_mode(self, mode: str):
        """Switch between sentence and Marungko reading materials."""
        if mode == self.active_mode:
            self.update_mode_buttons()
            self.update_stt_config_label()
            return

        if self.is_speech_active:
            self.stop_speech()

        self.active_mode = mode
        self.sentences = self.SAMPLE_SENTENCES.copy() if mode == "sentence" else self.MARUNGKO_MATERIALS.copy()
        self.current_sentence_index = 0
        self.current_word_index = 0
        self.current_syllable_index = 0
        self.raw_transcript_display.clear()
        self.progress_bar.setValue(0)
        self.update_mode_buttons()
        self.update_stt_config_label()
        self.load_sentence()
        self.status_label.setText(f"{self.mode_title()} mode loaded - Ready to read")

    def update_mode_buttons(self):
        """Reflect the active mode in the segmented controls."""
        self.sentence_mode_button.setChecked(self.active_mode == "sentence")
        self.marungko_mode_button.setChecked(self.active_mode == "marungko")
        if hasattr(self, "next_button"):
            self.next_button.setText("→ Next Sentence" if self.active_mode == "sentence" else "→ Next Marungko")

    def update_stt_config_label(self, extra: str = ""):
        """Show the active Google STT setup."""
        if not hasattr(self, "stt_config_label"):
            return

        if self.active_mode == "marungko":
            text = (
                f"STT: Google Chirp 3 V2 · {self.google_language_code()} · "
                f"{self.google_location()} · fallback: V1 phrase hints"
            )
        else:
            text = (
                f"STT: Google Chirp 3 V2 · {self.google_language_code()} · "
                f"{self.google_location()} · fallback: V1 latest_short"
            )

        if extra:
            text = f"{text} · {extra}"
        self.stt_config_label.setText(text)

    def mode_title(self) -> str:
        """Return the user-facing active mode name."""
        return "Sentence" if self.active_mode == "sentence" else "Marungko"

    @staticmethod
    def darken_color(hex_color: str, factor: float = 0.9) -> str:
        """Darken a hex color."""
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)

        r = int(r * factor)
        g = int(g * factor)
        b = int(b * factor)

        return f"#{r:02x}{g:02x}{b:02x}"

    def load_sentence(self):
        """Load the current sentence."""
        if self.current_sentence_index < len(self.sentences):
            sentence = self.sentences[self.current_sentence_index]
            self.words = sentence.split()
            self.current_word_index = 0
            self.current_syllable_index = 0
            self.build_syllable_index()
            self.update_display()
            self.update_counter()
            self.update_progress()

    def build_syllable_index(self):
        """Build a syllable stream and word-to-syllable ranges for the current sentence."""
        self.syllables = []
        self.word_syllable_ranges = []

        for word in self.words:
            start = len(self.syllables)
            word_syllables = self.split_syllables(self.normalize_word(word))
            self.syllables.extend(word_syllables)
            self.word_syllable_ranges.append((start, len(self.syllables)))

    def update_display(self):
        """Update the sentence display with syllable-level highlighting."""
        document = QTextDocument()
        cursor = QTextCursor(document)

        for idx, word in enumerate(self.words):
            if idx > 0:
                cursor.insertText(" ")

            start, end = self.word_syllable_ranges[idx]
            word_syllables = self.syllables[start:end] or [word]
            for offset, syllable in enumerate(word_syllables):
                if offset > 0:
                    cursor.insertText("-")

                syllable_index = start + offset
                if syllable_index < self.current_syllable_index:
                    fmt = self.create_text_format("#4CAF50", 600, 18, "#E7F7EC")
                elif syllable_index == self.current_syllable_index:
                    fmt = self.create_text_format("#0F172A", 700, 20, "#DDEBFF")
                else:
                    fmt = self.create_text_format("#243B53", 400, 18)
                cursor.insertText(syllable, fmt)

        self.sentence_display.setDocument(document)

    @staticmethod
    def create_text_format(
        color: str,
        weight: int,
        point_size: int,
        background: str | None = None,
    ) -> QTextCharFormat:
        """Create a QTextCharFormat for syllable rendering."""
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        fmt.setFontWeight(weight)
        fmt.setFontPointSize(point_size)
        if background:
            fmt.setBackground(QColor(background))
        return fmt

    def update_progress(self):
        """Update the progress bar."""
        if self.syllables:
            progress = int((self.current_syllable_index / len(self.syllables)) * 100)
            self.progress_bar.setValue(progress)
        else:
            self.progress_bar.setValue(0)

    def update_counter(self):
        """Update the sentence counter label."""
        self.counter_label.setText(f"{self.mode_title()} {self.current_sentence_index + 1} of {len(self.sentences)}")

    def reset_reading(self):
        """Reset the current sentence to the beginning."""
        if self.is_speech_active:
            self.stop_speech()
        self.current_word_index = 0
        self.current_syllable_index = 0
        self.next_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.raw_transcript_display.clear()
        self.status_label.setText("Reset - Ready to start reading")
        self.update_display()

    def next_sentence(self):
        """Move to the next sentence."""
        if self.is_speech_active:
            self.stop_speech()
        self.current_sentence_index += 1

        if self.current_sentence_index >= len(self.sentences):
            self.current_sentence_index = 0

        self.next_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.raw_transcript_display.clear()
        self.status_label.setText(f"New {self.mode_title().lower()} loaded - Ready to read")
        self.load_sentence()

    def transcribe_speech(self):
        """Listen to spoken reading and highlight matching words."""
        if self.is_speech_active:
            self.stop_speech()
            return

        api_key = self.GOOGLE_API_KEY.strip()
        if not api_key:
            self.status_label.setText("Google Speech is not configured.")
            return

        os.environ["GOOGLE_API_KEY"] = api_key
        language_code = self.google_language_code()
        phrase_hints = self.google_phrase_hints()
        model = self.google_model()
        project_id = self.google_project_id()
        location = self.google_location()

        self.is_speech_active = True
        self.next_button.setEnabled(False)
        self.speech_button.setText("■ Stop")
        self.status_label.setText(f"Listening with Google Speech ({language_code})...")
        self.update_stt_config_label("listening")
        self.update_display()

        self.speech_thread = QThread()
        self.speech_worker = SpeechWorker(
            api_key,
            language_code=language_code,
            phrase_hints=phrase_hints,
            model=model,
            project_id=project_id,
            location=location,
            duration=3,
        )
        self.speech_worker.moveToThread(self.speech_thread)

        self.speech_thread.started.connect(self.speech_worker.run)
        self.speech_worker.status.connect(self.status_label.setText)
        self.speech_worker.transcript_ready.connect(self.handle_speech_transcript)
        self.speech_worker.error.connect(self.handle_speech_error)
        self.speech_worker.finished.connect(self.speech_thread.quit)
        self.speech_worker.finished.connect(self.speech_worker.deleteLater)
        self.speech_thread.finished.connect(self.speech_thread.deleteLater)
        self.speech_thread.finished.connect(self.finish_speech_worker)
        self.speech_thread.start()

    def google_language_code(self) -> str:
        """Return the Google STT language code for the active mode."""
        return "fil-PH" if self.active_mode == "marungko" else "en-US"

    def google_phrase_hints(self) -> list[str]:
        """Return Google STT phrase hints for the active mode."""
        return self.MARUNGKO_PHRASE_HINTS if self.active_mode == "marungko" else []

    def google_model(self) -> str:
        """Return the Google STT model for the active mode."""
        return "chirp_3"

    def google_project_id(self) -> str:
        """Return the Google Cloud project id for Speech-to-Text V2."""
        return os.environ.get("GOOGLE_CLOUD_PROJECT", self.GOOGLE_CLOUD_PROJECT_ID).strip()

    def google_location(self) -> str:
        """Return the Google Cloud location for Speech-to-Text V2."""
        return os.environ.get("GOOGLE_STT_LOCATION", self.GOOGLE_CHIRP_LOCATION).strip()

    def handle_speech_transcript(self, transcript: str):
        """Advance through the sentence for each correctly spoken word."""
        self.append_raw_transcript(transcript)
        matched = self.advance_for_spoken_text(transcript)

        if self.current_syllable_index >= len(self.syllables):
            self.finish_speech_sentence()
        elif matched:
            next_word = self.words[self.current_word_index]
            next_syllable = self.syllables[self.current_syllable_index]
            self.status_label.setText(
                f"Matched {matched} syllable{'s' if matched != 1 else ''}. Next: {next_syllable} in {next_word}"
            )
        else:
            self.status_label.setText(
                f"Try again from: {self.syllables[self.current_syllable_index]} in {self.words[self.current_word_index]}"
            )

    def handle_speech_error(self, message: str):
        """Show a speech capture or transcription error."""
        self.status_label.setText(f"Speech error: {message}")
        self.stop_speech(show_status=False)

    def finish_speech_worker(self):
        """Restore speech controls after the worker thread exits."""
        self.is_speech_active = False
        self.speech_button.setText("🎤 Speak")
        self.next_button.setEnabled(True)
        self.speech_thread = None
        self.speech_worker = None
        self.update_stt_config_label()
        self.update_display()

    def append_raw_transcript(self, transcript: str):
        """Print raw microphone text and derived syllables below the reading material."""
        syllables = self.format_syllables_for_text(transcript)
        self.raw_transcript_display.append(f"Words: {transcript}")
        if syllables:
            self.raw_transcript_display.append(f"Syllables: {syllables}")
        self.raw_transcript_display.append("")

    def stop_speech(self, show_status: bool = True):
        """Request speech listening to stop."""
        if self.speech_worker:
            self.speech_worker.stop()
        if show_status:
            self.status_label.setText("Stopping speech check...")

    def finish_speech_sentence(self):
        """Stop listening after the displayed material has been read correctly."""
        self.progress_bar.setValue(100)
        self.status_label.setText("Great job! You finished the sentence.")
        self.stop_speech(show_status=False)

    def advance_for_spoken_text(self, transcript: str) -> int:
        """Highlight spoken syllables that continue the displayed text."""
        spoken_syllables = self.syllables_for_text(transcript)
        return self.advance_for_syllables(spoken_syllables)

    def advance_for_syllables(self, spoken_syllables: list[str]) -> int:
        """Highlight spoken syllables that continue the displayed text."""
        if not spoken_syllables or self.current_syllable_index >= len(self.syllables):
            return 0

        new_syllable_index = self.find_best_read_position(spoken_syllables, self.syllables)
        if new_syllable_index <= self.current_syllable_index:
            return 0

        matched = new_syllable_index - self.current_syllable_index
        self.current_syllable_index = new_syllable_index
        self.current_word_index = self.word_index_for_syllable(self.current_syllable_index)
        if matched:
            self.update_display()
            self.update_progress()

        return matched

    def find_best_read_position(self, spoken_words: list[str], target_words: list[str]) -> int:
        """Find the farthest target syllable position confirmed by the latest speech chunk."""
        best_index = self.current_syllable_index
        first_candidate = max(0, self.current_syllable_index - len(spoken_words) - 3)
        last_candidate = self.current_syllable_index

        for target_start in range(first_candidate, last_candidate + 1):
            spoken_index = 0
            target_index = target_start

            while spoken_index < len(spoken_words) and target_index < len(target_words):
                if self.words_match(spoken_words[spoken_index], target_words[target_index]):
                    target_index += 1
                spoken_index += 1

            if target_index > best_index:
                best_index = target_index

        return best_index

    def words_match(self, spoken_word: str, target_word: str) -> bool:
        """Return whether speech recognition likely matches the target word."""
        if spoken_word == target_word:
            return True

        if self.cv_syllables_sound_match(spoken_word, target_word):
            return True

        longer = max(len(spoken_word), len(target_word))
        if longer <= 3:
            return False

        allowed_distance = 1 if longer <= 5 else 2
        return self.edit_distance(spoken_word, target_word, allowed_distance) <= allowed_distance

    @classmethod
    def cv_syllables_sound_match(cls, spoken_word: str, target_word: str) -> bool:
        """Match Marungko-style consonant-vowel syllables by likely STT sound."""
        target = cls.cv_parts(target_word)
        if not target:
            return False

        target_consonant, target_vowel = target
        aliases = cls.VOWEL_SOUND_ALIASES.get(target_vowel, {target_vowel})

        for spoken_variant in cls.spoken_sound_variants(spoken_word):
            spoken = cls.cv_parts(spoken_variant)
            if not spoken:
                continue

            spoken_consonant, spoken_vowel = spoken
            if spoken_consonant == target_consonant and spoken_vowel in aliases:
                return True

        return False

    @classmethod
    def cv_parts(cls, syllable: str) -> tuple[str, str] | None:
        """Return consonant and vowel for a simple CV syllable."""
        if len(syllable) < 2:
            return None
        consonant = syllable[:-1]
        vowel = syllable[-1]
        if vowel not in cls.VOWELS:
            return None
        if not consonant or any(char in cls.VOWELS for char in consonant):
            return None
        return consonant, vowel

    @staticmethod
    def spoken_sound_variants(word: str) -> set[str]:
        """Return likely simple-syllable spellings for an STT word."""
        variants = {word}
        if len(word) > 1 and word.endswith("y"):
            variants.add(f"{word[:-1]}i")
        return variants

    @staticmethod
    def edit_distance(left: str, right: str, max_distance: int) -> int:
        """Compute bounded Levenshtein distance for short word comparisons."""
        if abs(len(left) - len(right)) > max_distance:
            return max_distance + 1

        previous = list(range(len(right) + 1))
        for left_index, left_char in enumerate(left, start=1):
            current = [left_index]
            row_min = current[0]
            for right_index, right_char in enumerate(right, start=1):
                cost = 0 if left_char == right_char else 1
                current.append(
                    min(
                        previous[right_index] + 1,
                        current[right_index - 1] + 1,
                        previous[right_index - 1] + cost,
                    )
                )
                row_min = min(row_min, current[-1])

            if row_min > max_distance:
                return max_distance + 1
            previous = current

        return previous[-1]

    @staticmethod
    def normalize_word(word: str) -> str:
        """Normalize a word for speech-to-text comparison."""
        return re.sub(r"[^a-z0-9']", "", word.lower())

    @classmethod
    def normalize_words(cls, text: str) -> list[str]:
        """Split recognized speech into normalized words."""
        return [word for word in (cls.normalize_word(part) for part in text.split()) if word]

    @classmethod
    def syllables_for_text(cls, text: str) -> list[str]:
        """Convert text into a flat syllable stream."""
        syllables = []
        for word in cls.normalize_spoken_words(text):
            syllables.extend(cls.split_syllables(word))
        return syllables

    def word_index_for_syllable(self, syllable_index: int) -> int:
        """Return the word index that contains the current syllable."""
        if syllable_index >= len(self.syllables):
            return len(self.words)

        for word_index, (start, end) in enumerate(self.word_syllable_ranges):
            if start <= syllable_index < end:
                return word_index

        return 0

    @classmethod
    def format_syllables_for_text(cls, text: str) -> str:
        """Create a display-friendly syllable breakdown for recognized speech."""
        syllable_words = []
        for word in cls.normalize_spoken_words(text):
            syllables = cls.split_syllables(word)
            if syllables:
                syllable_words.append("-".join(syllables))
        return " / ".join(syllable_words)

    @classmethod
    def normalize_spoken_words(cls, text: str) -> list[str]:
        """Normalize STT words, including vowel sounds like 'ohhh' -> 'o'."""
        words = []
        for word in cls.normalize_words(text):
            words.append(cls.normalize_spoken_word(word))
        return [word for word in words if word]

    @classmethod
    def normalize_spoken_word(cls, word: str) -> str:
        """Convert common speech-to-text vowel names into the intended vowel."""
        vowel_syllable = cls.normalize_spoken_vowel_syllable(word)
        if vowel_syllable:
            return vowel_syllable

        collapsed = cls.collapse_repeated_letters(word)
        if collapsed in cls.SPOKEN_VOWELS:
            return cls.SPOKEN_VOWELS[collapsed]
        return word

    @classmethod
    def normalize_spoken_vowel_syllable(cls, word: str) -> str:
        """Normalize English-ish STT spellings of simple CV syllables."""
        match = re.fullmatch(r"([^aeiou]+)ah", word)
        if match:
            return f"{match.group(1)}a"

        match = re.fullmatch(r"([^aeiou]+)eh", word)
        if match:
            return f"{match.group(1)}e"

        match = re.fullmatch(r"([^aeiou]+)oh", word)
        if match:
            return f"{match.group(1)}o"

        match = re.fullmatch(r"([^aeiou]+)uh", word)
        if match:
            return f"{match.group(1)}u"

        match = re.fullmatch(r"([^aeiou]+)(ee|ea|ey|ie)", word)
        if match:
            return f"{match.group(1)}i"

        match = re.fullmatch(r"([^aeiou]+)(oo|ew|ue)", word)
        if match:
            return f"{match.group(1)}u"

        match = re.fullmatch(r"([^aeiou]+)(oe|ow|oa)", word)
        if match:
            return f"{match.group(1)}o"

        return ""

    @staticmethod
    def collapse_repeated_letters(word: str) -> str:
        """Collapse stretched STT words such as 'ohhh' or 'aaa'."""
        return re.sub(r"(.)\1+", r"\1", word)

    @classmethod
    def split_syllables(cls, word: str) -> list[str]:
        """Split a normalized word into rough readable syllables."""
        if not word:
            return []
        if not any(char in cls.VOWELS for char in word):
            return [word]

        syllables = []
        current = ""
        index = 0
        while index < len(word):
            current += word[index]
            if word[index] in cls.VOWELS:
                next_char = word[index + 1] if index + 1 < len(word) else ""
                next_next = word[index + 2] if index + 2 < len(word) else ""

                if not next_char:
                    syllables.append(current)
                    current = ""
                elif next_char in cls.VOWELS:
                    syllables.append(current)
                    current = ""
                elif next_next and next_next in cls.VOWELS:
                    syllables.append(current)
                    current = ""
                elif cls.has_final_consonant_cluster(word, index):
                    syllables.append(current)
                    current = ""
                elif index + 1 == len(word) - 1:
                    current += next_char
                    syllables.append(current)
                    current = ""
                    index += 1
            index += 1

        if current:
            syllables.append(current)

        return syllables

    @classmethod
    def has_final_consonant_cluster(cls, word: str, vowel_index: int) -> bool:
        """Return whether a vowel is followed by a multi-letter final consonant tail."""
        tail = word[vowel_index + 1 :]
        return len(tail) > 1 and all(char not in cls.VOWELS for char in tail)

    def record_microphone_audio(self, duration: float = 5.0) -> str:
        """Record microphone audio into a temporary WAV file."""
        return record_microphone_audio(duration)

    def transcribe_audio_file(self, audio_path: str, api_key: str) -> str:
        """Send recorded audio to Google Cloud Speech-to-Text using an API key."""
        return transcribe_audio_file(
            audio_path,
            api_key,
            self.google_language_code(),
            self.google_phrase_hints(),
            self.google_model(),
            self.google_project_id(),
            self.google_location(),
        )


def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 11))

    window = WordFlowReader()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
