# syntax=docker/dockerfile:1
# ---- Gateway : build frontend (Vite) puis service Nginx routage ----
FROM node:22-alpine AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/index.html frontend/vite.config.ts frontend/tsconfig.json frontend/tsconfig.app.json frontend/tsconfig.node.json ./
COPY frontend/public ./public
COPY frontend/src ./src
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY docker/gateway/nginx.conf /etc/nginx/nginx.conf
COPY --from=frontend /src/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=4s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/health || exit 1
