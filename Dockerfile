FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY agent/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt && useradd --create-home --uid 10001 app

COPY --chown=app agent/ /app/agents/agent/
USER app

CMD ["sh", "-c", "exec adk web --host 0.0.0.0 --port ${PORT:-8080} /app/agents"]
