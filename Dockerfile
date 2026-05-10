FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./

RUN uv sync --frozen --no-dev

CMD ["uv", "run", "--frozen", "--no-dev", "linkdooni"]
