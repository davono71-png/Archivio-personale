FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -e .

CMD ["python", "-m", "gmail_drive_archiver.dashboard_api", "--host", "0.0.0.0", "--port", "8090", "--db", "database/personal-archive.sqlite3"]
