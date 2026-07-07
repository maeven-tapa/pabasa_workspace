import os
import shutil
from django.apps import AppConfig


class PabasaAppConfig(AppConfig):
    name = 'pabasa_app'

    def ready(self):
        """Initialize app and configure Tesseract OCR path."""
        self._configure_tesseract()

    @staticmethod
    def _configure_tesseract():
        """Set pytesseract tesseract_cmd to locate Tesseract executable."""
        try:
            import pytesseract
        except ImportError:
            return

        # Check if already configured to a valid path (not the default 'tesseract' string)
        current_cmd = pytesseract.pytesseract.tesseract_cmd
        if current_cmd and current_cmd != 'tesseract' and os.path.isfile(current_cmd):
            return

        # Try environment variables first
        tesseract_cmd = os.environ.get('TESSERACT_CMD') or os.environ.get('TESSERACT_PATH')
        if tesseract_cmd and os.path.isfile(tesseract_cmd):
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            return

        # Try system PATH
        try:
            resolved = shutil.which('tesseract')
            if resolved:
                pytesseract.pytesseract.tesseract_cmd = resolved
                return
        except Exception:
            pass

        # Try common Windows paths
        common_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            os.path.expandvars(r'%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe'),
            os.path.expandvars(r'%ProgramFiles%\Tesseract-OCR\tesseract.exe'),
        ]
        for path in common_paths:
            if path and os.path.isfile(path):
                pytesseract.pytesseract.tesseract_cmd = path
                return
