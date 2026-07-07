# Backend meta-bot-core: uv-управляемый образ (равнение на sro-agent-core).
# Версия приложения приходит из CI аргументом (hatch-vcs без .git в контексте).
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ARG APP_VERSION=0.0.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${APP_VERSION} \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/tmp/uv-cache

WORKDIR /app

# Слои кэшируются: сначала зависимости по lock-файлу, потом код проекта.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/tmp/uv-cache \
    uv sync --frozen --no-install-project --no-dev

COPY src/ ./src/
RUN --mount=type=cache,target=/tmp/uv-cache \
    uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
