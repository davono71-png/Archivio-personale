FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ocrmypdf \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-ita \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -e .

CMD ["gmail-drive-archiver", "ocr-plan", "--input", "database/inventory-da-classificare.csv"]
