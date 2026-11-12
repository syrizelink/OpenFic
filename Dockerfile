# syntax=docker/dockerfile:1

# ---- 前端构建：固定到构建平台（amd64）一次构建，产物与架构无关 ----
FROM --platform=$BUILDPLATFORM node:22-slim AS frontend
WORKDIR /build
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN --mount=type=cache,id=pnpm-store,target=/pnpm/store \
    pnpm install --frozen-lockfile --store-dir /pnpm/store
COPY frontend/ ./
RUN pnpm build

# Build the optional collaboration worker as a self-contained Node bundle.
WORKDIR /collaboration
COPY collaboration/package.json collaboration/pnpm-lock.yaml collaboration/pnpm-workspace.yaml ./
RUN --mount=type=cache,id=pnpm-store,target=/pnpm/store \
    pnpm install --frozen-lockfile --store-dir /pnpm/store
COPY collaboration/ ./
RUN pnpm build

# Node runtime must match the target architecture (frontend builds on BUILDPLATFORM).
FROM node:22-slim AS collaboration-runtime

# ---- 后端运行：按目标平台构建（amd64 / arm64）----
FROM python:3.12-slim AS backend

ARG OPENFIC_EXTRA=

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

WORKDIR /app
RUN apt-get update \
    && apt-get install --no-install-recommends -y libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=collaboration-runtime /usr/local/bin/node /usr/local/bin/node

# 先装依赖（利用层缓存）
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv \
    if [ -n "$OPENFIC_EXTRA" ]; then \
        uv sync --frozen --no-dev --no-install-project --extra "$OPENFIC_EXTRA"; \
    else \
        uv sync --frozen --no-dev --no-install-project; \
    fi

# 复制后端源码
COPY backend/ ./

# 安装当前项目以写入发行版元数据，供运行时读取版本号
RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv \
    if [ -n "$OPENFIC_EXTRA" ]; then \
        uv sync --frozen --no-dev --extra "$OPENFIC_EXTRA"; \
    else \
        uv sync --frozen --no-dev; \
    fi

# 前端构建产物打入包内
COPY --from=frontend /build/dist ./app/frontend_dist
COPY --from=frontend /backend/app/collaboration/server.bundle.cjs ./app/collaboration/server.bundle.cjs

ENV OPENFIC_FRONTEND_DIST=/app/app/frontend_dist \
    OPENFIC_DATA_DIR=/data

RUN mkdir -p /data

EXPOSE 8000

CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
