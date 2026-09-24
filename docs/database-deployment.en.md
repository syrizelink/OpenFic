# First deployment and database selection

[中文](database-deployment.zh-CN.md) · [Migration and rollback](database-migration.en.md)

These instructions apply to the source revision containing this feature. Published packages/images from older releases do not necessarily include it. For this unreleased change, use this checkout with `uv sync --frozen`, or build its Dockerfile. Use the same application revision for all migration and runtime commands.

## Choose before the first start

| Business data | Agent checkpoints | Configuration | Typical use |
| --- | --- | --- | --- |
| SQLite | SQLite | Neither variable set | Default desktop or single-instance local installation |
| PostgreSQL | PostgreSQL | Both variables set | Self-hosting with separately managed relational storage |
| PostgreSQL | SQLite | Only `OPENFIC_DATABASE_URL` | Move business data while retaining local Agent history |
| SQLite | PostgreSQL | Only `OPENFIC_CHECKPOINT_DATABASE_URL` | Separate checkpoint storage while keeping business data local |

A database choice does not enable multi-user isolation, multiple application replicas, or distributed workers. Continue running one application instance. LanceDB, uploaded files, exports, configuration, and the encryption key remain in `OPENFIC_DATA_DIR` in every mode. PostgreSQL does not replace this persistent directory. Never expose the app without appropriate access control; the existing `OPENFIC_AUTH_PASSWORD` option is available.

Selection is made when the process starts. Changing a URL selects another database; it does **not** copy existing data. Stop the app before switching and use the migration guide for populated installations. Invalid schemes/drivers fail validation; an unavailable PostgreSQL server does not cause fallback to SQLite.

## Option A: SQLite (default)

No PostgreSQL server is required. Leave `OPENFIC_DATABASE_URL` and `OPENFIC_CHECKPOINT_DATABASE_URL` unset (empty values also select the defaults). Remove stale entries from the data directory's `.env` as well as the service environment.

Docker retains the existing default:

```bash
docker compose up -d
```

To run this exact checkout instead of the published image:

```bash
docker build -t openfic:local .
docker run -d --name openfic -p 127.0.0.1:8000:8000 -v openfic:/data openfic:local
```

For a source installation, use Python 3.12 or 3.13 and uv:

```bash
cd backend
uv sync --frozen
export OPENFIC_DATA_DIR="$HOME/.openfic"
uv run --frozen openfic upgrade-database
uv run --frozen openfic serve
```

`upgrade-database` runs business-schema migrations without starting the server, seed routines, or background workers. Starting the server also runs these migrations automatically. The CLI defaults to `~/.openfic`; Docker uses `/data`; direct `uvicorn app.main:app` uses `backend/data` unless `OPENFIC_DATA_DIR` is set. Specify the directory explicitly to avoid opening the wrong installation.

## Option B: PostgreSQL with Docker Compose

For a **new** deployment, from the repository root:

```bash
# Generate a URL-safe password; save it in your deployment secret store for subsequent commands.
export OPENFIC_POSTGRES_PASSWORD="$(openssl rand -hex 24)"
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

The override builds the current checkout, enables both database URLs, starts PostgreSQL 17, and creates `openfic_app` and `openfic_checkpoint`. PostgreSQL has no published host port. Business data and checkpoints use a PostgreSQL volume; `/data` keeps a separate volume. Back up both.

The initialization SQL runs only on a new PostgreSQL volume. Changing the password variable later does not rotate an existing database role's password. For an existing PostgreSQL volume, provision the checkpoint database and credentials explicitly rather than deleting the volume. When using a managed server, create separate business/checkpoint databases, give the application role ownership of its schemas and permission for startup DDL/index migrations, and set the URLs directly instead of starting the bundled server.

Do not run this command against an existing SQLite deployment expecting an automatic migration. Use [the migration guide](database-migration.en.md).

## Option C: source/package deployment with an existing PostgreSQL server

Create two empty, dedicated databases owned by your application role. Example as an authorized PostgreSQL administrator:

```bash
createdb -O openfic openfic_app
createdb -O openfic openfic_checkpoint
```

Install from this checkout as above. In the application's service environment, set:

```bash
export OPENFIC_DATA_DIR='/absolute/path/to/openfic-data'
export OPENFIC_DATABASE_URL='postgresql+psycopg://openfic:URL_ENCODED_PASSWORD@db-host:5432/openfic_app'
export OPENFIC_CHECKPOINT_DATABASE_URL='postgresql://openfic:URL_ENCODED_PASSWORD@db-host:5432/openfic_checkpoint'
uv run --frozen openfic upgrade-database
uv run --frozen openfic serve --host 0.0.0.0
```

The placeholders above must be replaced. Percent-encode reserved characters in username/password (`@` → `%40`, `%` → `%25`); keep real credentials in restricted environment files or your secret manager. Both URLs accept `postgresql://` and `postgresql+psycopg://`; `postgresql+psycopg_async://` is normalized too. Other PostgreSQL drivers are not supported. Psycopg connection query parameters such as `sslmode=verify-full&sslrootcert=/path/to/ca.pem` may be used for remote servers. Sessions use UTC. The packaged dependencies include the driver, but the default SQLite mode never connects to PostgreSQL.

The runtime also reads `OPENFIC_DATA_DIR/.env`. Process environment takes precedence. The migration CLI target is read from an **exported process variable**, not that `.env` file. Keep business and checkpoint databases separate so lifecycle and migration checks remain independent.

## Acceptance and operations

1. Check startup logs for completed schema migration and no connection/setup errors. `curl --fail http://127.0.0.1:8000/api/v1/health` checks HTTP availability; it alone does not prove persistence works.
2. Create a project, rename it, search by Chinese/pinyin, and reopen it after a restart.
3. With a configured model, run an Agent turn, restart, inspect its messages, and run another turn; check attachment reading and revision rollback.
4. Inspect dashboard/writing-day totals in the intended timezone.
5. Back up the business database, checkpoint database, and **the full data directory including `.key`** as one stopped-instance snapshot. Use `pg_dump -Fc` / `pg_restore` for PostgreSQL, and a consistent SQLite backup or whole-directory copy after shutdown for SQLite.

Automated validation and known boundaries are recorded in [database-validation.md](database-validation.md). Model-provider calls and production restore drills require your own deployment acceptance. PostgreSQL 17 is the tested baseline; other major versions are not established by these tests.
