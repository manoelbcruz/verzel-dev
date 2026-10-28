# Imagem de produção: a API serve o build do front numa única origem, num único processo.
FROM node:24-alpine AS front

WORKDIR /front
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /uvx /bin/

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never \
    FRONTEND_DIST=/app/static

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-cache

COPY backend/ ./
COPY --from=front /front/dist ./static
RUN useradd --create-home app
USER app

EXPOSE 8000
# Um único worker: a central do WebSocket vive em memória.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --ws-max-size 65536 --proxy-headers --forwarded-allow-ips='*'"]
