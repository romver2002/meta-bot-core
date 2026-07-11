# Backend meta-bot-core: uv-управляемый образ (равнение на sro-agent-core).
# Non-root: процесс работает под пользователем app; версия приложения — из CI
# аргументом (hatch-vcs без .git в контексте).
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ARG APP_VERSION=0.0.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${APP_VERSION} \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_PYTHON_PREFERENCE=only-system \
    UV_NO_SYNC=1

RUN groupadd --system app && useradd --system --gid app --uid 10001 app

WORKDIR /app

# Слои кэшируются: сначала зависимости по lock-файлу, потом код проекта.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/tmp/uv-cache \
    UV_NO_SYNC=0 uv sync --frozen --no-install-project --no-dev

COPY src/ ./src/
COPY alembic.ini ./
COPY migrations/ ./migrations/
COPY ops/certs/russian_trusted_root_ca.pem ./ops/certs/
RUN --mount=type=cache,target=/tmp/uv-cache \
    UV_NO_SYNC=0 uv sync --frozen --no-dev \
    # Сертификат Минцифры в certifi: без него исходящие в platform-api2.max.ru
    # падают по TLS (раньше добавлялся вручную и терялся при пересоздании).
    && cat ops/certs/russian_trusted_root_ca.pem >> "$(uv run python -c 'import certifi; print(certifi.where())')" \
    && chown -R app:app /app

# Runtime-кэш uv — в путь, который непривилегированный app может создать
# (/tmp/uv-cache остаётся в слое root-owned от build-стадии).
ENV UV_CACHE_DIR=/tmp/uv-app-cache

USER app
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
