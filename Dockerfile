# Sanuvia Persistent Reasoning Core — engineering review harness.
# Standard-library only at runtime: no framework, no cloud SDK. Deployment-agnostic.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SANUVIA_HOST=0.0.0.0 \
    SANUVIA_PORT=8000 \
    SANUVIA_BACKEND=memory \
    SANUVIA_DB_PATH=/data/sanuvia.db \
    SANUVIA_TESTCASE_DIR=/data/testcases

WORKDIR /app

# Install the package (core has zero runtime dependencies).
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . \
    && mkdir -p /data \
    && useradd -m app \
    && chown -R app /data

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)" || exit 1

CMD ["python", "-m", "sanuvia.adapters.http.server"]
