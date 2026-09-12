# syntax=docker/dockerfile:1

# ---- Build frontend: dipaku ke platform build (amd64), sekali build, hasilnya lepas dari arsitektur ----
FROM --platform=$BUILDPLATFORM node:22-slim AS frontend
WORKDIR /build
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
COPY frontend/patches/ ./patches/
RUN --mount=type=cache,id=pnpm-store,target=/pnpm/store \
    pnpm install --frozen-lockfile --store-dir /pnpm/store
COPY frontend/ ./
RUN pnpm build

# ---- Runtime backend: dibangun sesuai platform target (amd64 / arm64) ----
FROM python:3.12-slim AS backend

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

WORKDIR /app

# Pasang dependensi lebih dulu (memanfaatkan cache layer)
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Salin kode sumber backend
COPY backend/ ./

# Pasang proyek ini agar metadata distribusi tertulis, supaya nomor versi terbaca saat runtime
RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Masukkan hasil build frontend ke dalam paket
COPY --from=frontend /build/dist ./app/frontend_dist

ENV OPENFIC_FRONTEND_DIST=/app/app/frontend_dist \
    OPENFIC_DATA_DIR=/data

RUN mkdir -p /data

EXPOSE 8000

CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
