# syntax=docker/dockerfile:1
# ---- Image notifications : multi-stage, non-root, < 200 Mo ----
FROM python:3.12-slim AS deps
WORKDIR /build
COPY requirements-prod.txt ./
RUN python -m pip install --no-cache-dir --prefix=/install -r requirements-prod.txt

FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 10001 appuser
COPY --from=deps /install /usr/local

WORKDIR /app
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN chown -R appuser:appuser /app

USER appuser
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; u=urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4); sys.exit(0 if u.status in (200,503) else 1)"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
