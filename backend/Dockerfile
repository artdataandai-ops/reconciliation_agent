# Reconciliation Exception Agent — backend image.
# Build context is the REPO ROOT (see docker-compose.yml: context: ., dockerfile: backend/Dockerfile)
# because main.py resolves the dataset generator at ../gen_unrecon_day.py.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Deps first for layer caching.
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# App code: the flat backend package + the dataset generator (resolved at /app/gen_unrecon_day.py).
COPY backend/ ./backend/
COPY gen_unrecon_day.py ./

# Generated dataset lives here (volume-mounted in compose; AUTO_REGEN recreates it).
RUN mkdir -p /app/data

EXPOSE 8000

# Single worker: the app regenerates dataset files on startup and on the first request of a
# new day, so multiple workers could race on those writes. Plenty for a demo's traffic.
CMD ["uvicorn", "main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
