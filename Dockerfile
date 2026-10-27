FROM node:24-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FRONTEND_DIST=/app/frontend/dist

WORKDIR /app
COPY agent/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt && useradd --create-home --uid 10001 app

COPY --chown=app agent/ /app/agent/
COPY --chown=app --from=frontend /build/dist /app/frontend/dist
USER app
WORKDIR /app/agent

CMD ["sh", "-c", "exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080}"]
