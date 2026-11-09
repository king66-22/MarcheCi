# syntax=docker/dockerfile:1
# ---- Image catalogue : multi-stage, non-root, < 200 Mo ----
# Alpine = base ~60 Mo ; les dépendances binaires utilisent des wheels musllinux.
FROM python:3.12-alpine@sha256:e6dae589c1c05976188fd3bd019afd091445fc533ed2ea29001beddc7368a9c8 AS deps
WORKDIR /build
COPY requirements-prod.txt ./
RUN python -m pip install --no-cache-dir --prefix=/install -r requirements-prod.txt

FROM python:3.12-alpine@sha256:e6dae589c1c05976188fd3bd019afd091445fc533ed2ea29001beddc7368a9c8 AS runtime
# Utilisateur applicatif dédié, UID > 10 000 (non-root exigé)
RUN addgroup -g 10001 appgroup && adduser -D -H -u 10001 -G appgroup appuser
COPY --from=deps /install /usr/local

WORKDIR /app
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
# Volume partagé des photos : le dossier doit appartenir à appuser pour que le
# volume Docker nommé (media_data) soit inscriptible dès sa première création.
RUN mkdir -p /data/media/products \
    && chown -R appuser:appgroup /app /data

USER appuser
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request,sys; u=urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4); sys.exit(0 if u.status in (200,503) else 1)"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
