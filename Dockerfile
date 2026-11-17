# syntax=docker/dockerfile:1
# ---------- Stage 1: build Tailwind CSS + vendor JS (no CDN at runtime) ----------
FROM node:20-alpine AS assets
WORKDIR /build
COPY package.json ./
RUN npm install --no-audit --no-fund --loglevel=error
COPY tailwind.config.js ./
COPY static/src ./static/src
COPY templates ./templates
COPY apps ./apps
RUN npx tailwindcss -c tailwind.config.js -i static/src/app.css -o out/dist/app.css --minify \
 && mkdir -p out/vendor/leaflet \
 && cp node_modules/htmx.org/dist/htmx.min.js out/vendor/ \
 && cp node_modules/alpinejs/dist/cdn.min.js out/vendor/alpine.min.js \
 && cp node_modules/chart.js/dist/chart.umd.js out/vendor/ \
 && cp node_modules/sortablejs/Sortable.min.js out/vendor/ \
 && cp -r node_modules/leaflet/dist/. out/vendor/leaflet/

# ---------- Stage 2: Python app ----------
FROM python:3.12-slim
ARG INSTALL_DEV=false
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Kolkata \
    STATIC_BUILD_DIR=/opt/static_build \
    STATIC_ROOT=/app/staticfiles \
    PRIVATE_MEDIA_ROOT=/app/private_media
WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN if [ "$INSTALL_DEV" = "true" ]; then pip install -r requirements-dev.txt; else pip install -r requirements.txt; fi
COPY . .
COPY --from=assets /build/out /opt/static_build
RUN useradd --create-home --uid 1000 app \
 && mkdir -p /app/staticfiles /app/private_media \
 && chown -R app:app /app /opt/static_build \
 && chmod +x /app/docker/entrypoint.sh
USER app
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60", "--access-logfile", "-"]
