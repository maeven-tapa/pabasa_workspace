FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
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
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000

CMD ["sh", "-c", "gunicorn pabasa_site.wsgi:application --chdir pabasa_site --worker-tmp-dir /dev/shm --bind 0.0.0.0:${PORT:-10000}"]
