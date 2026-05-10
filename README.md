# LinkDooni

LinkDooni is an async Python Telegram bot for Iranian users and small work teams who organize business links inside Telegram. Users can save links, categorize them, fetch previews, search, edit, delete, favorite, import, and export their data without leaving a chat.

Storage is PostgreSQL, run locally via Docker. The repository layer is async SQLAlchemy.

## Features

- Persian and English messages from YAML configuration
- `/start`, `/help`, `/categories`, `/add`, `/search`, `/favorites`, `/export`, `/settings`, and `/import`
- Category create, rename, delete with confirmation, and link browsing
- Direct and forwarded URL messages, including multiple URLs in one message
- Metadata fetching for title, description, canonical URL, Open Graph image, and favicon
- Safe URL fetching with timeouts, response-size limits, safe redirects, and private/internal IP blocking
- Link edit, move, delete, refresh preview, tags, notes, favorites, and duplicate detection
- JSON/CSV export and JSON import
- Async SQLAlchemy repositories, Alembic migrations, Ruff, pre-commit, and tests

## Create a Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather).
2. Run `/newbot`.
3. Choose a display name, for example `LinkDooni`.
4. Choose a unique username ending in `bot`.
5. Copy the token BotFather gives you.

Never commit the real token. Put it in `.env`.

## Setup

Install dependencies with uv:

```bash
uv sync --dev
```

Create your environment file:

```bash
cp .env.example .env
```

Set the token in `.env`:

```bash
TELEGRAM_BOT_TOKEN=123456789:your-real-token
```

The default `DATABASE_URL` in `.env.example` points at the local Docker Postgres:

```bash
DATABASE_URL=postgresql+asyncpg://linkdooni:linkdooni@localhost:5432/linkdooni
```

Start PostgreSQL via Docker Desktop:

```bash
make db-up
```

Run migrations:

```bash
make migrate
```

Run the bot:

```bash
make run
```

Stop the database:

```bash
make db-down
```

The Docker service is defined in `docker-compose.yml`.

## Development

Install pre-commit hooks:

```bash
uv run pre-commit install
```

Run linting:

```bash
make lint
```

Format code:

```bash
make format
```

Run tests (requires `make db-up` first; one-time `make db-test-create` to create the `linkdooni_test` database):

```bash
make db-test-create
make test
```

Create a migration after model changes:

```bash
make revision m="describe change"
make migrate
```

## Configuration

Application copy and labels live in `app/config/messages.yaml`.

Feature flags and language defaults live in `app/config/features.yaml`:

```yaml
enable_ai_summary: false
enable_team_workspaces: false
enable_link_health_check: false
enable_import_export: true
default_language: fa
```

Secrets and deployment-specific values come from environment variables.

## Deployment

For a simple VPS deployment, run the bot in long polling mode behind a process manager such as systemd:

```bash
uv sync --no-dev
uv run alembic upgrade head
uv run linkdooni
```

The bot is structured so webhook support can be added later without changing handlers: the dispatcher, routers, middleware, services, and repositories are already separated.

## Project Structure

```text
app/
  main.py
  bot/
  config/
  db/
  services/
  utils/
migrations/
tests/
```
