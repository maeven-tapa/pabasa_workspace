FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    OCR_LANGUAGES=eng+fil \
    OCR_TIMEOUT_SECONDS=15

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-fil \
    && rm -rf /var/lib/apt/lists/* \
    && tesseract --list-langs

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

# WhiteNoise serves these generated static assets in production.
RUN python pabasa_site/manage.py collectstatic --noinput

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8080') + '/', timeout=3)" || exit 1

# Apply schema updates before serving the application. `exec` lets Gunicorn
# receive container stop/restart signals directly.
CMD ["sh", "-c", "python pabasa_site/manage.py migrate --noinput && exec gunicorn pabasa_site.wsgi:application --chdir pabasa_site --worker-tmp-dir /dev/shm --bind 0.0.0.0:${PORT:-8080}"]
