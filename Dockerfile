FROM python:3.14.3-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ARG APP_PORT=8000
WORKDIR /code
ENV PYTHONPATH=/code \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# uvicorn[standard] тянет httptools/uvloop; для Python 3.14 часто нет готовых wheels — нужна сборка из исходников
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY ./pyproject.toml ./uv.lock /code/
RUN uv sync --frozen --no-dev --no-install-project
ENV PATH="/code/.venv/bin:$PATH"

COPY ./app /code/app
COPY ./migration /code/migration
COPY ./alembic.ini /code/alembic.ini

# Процессы приложения не работают под root
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

EXPOSE ${APP_PORT}
# Миграции применяются отдельным сервисом `migrate` (см. compose.yml)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT}"]