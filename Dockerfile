FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TESSERACT_CMD=/usr/bin/tesseract

# Install OCR and its English language data in the runtime image. A system-wide
# install keeps the executable and its shared libraries in matching locations.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        tesseract-ocr \
        tesseract-ocr-eng \
    && tesseract --version \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/pabasa_site

COPY requirements.txt /workspace/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /workspace/requirements.txt

COPY pabasa_site/ /workspace/pabasa_site/

RUN python manage.py collectstatic --noinput

EXPOSE 8080

CMD ["sh", "-c", "gunicorn pabasa_site.wsgi:application --bind 0.0.0.0:${PORT:-8080}"]
