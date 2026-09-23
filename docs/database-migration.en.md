# SQLite → PostgreSQL migration and rollback

[中文](database-migration.zh-CN.md) · [First deployment](database-deployment.en.md)

This is an offline, one-way business-database migration, not live replication. Use the exact same source revision for schema upgrade, copy, and application startup. The command never changes the runtime configuration for you. No production database is modified by the automated tests.

## What moves, what stays

The tool copies the current business schema (projects, chapters, messages, revisions, attachment metadata/extracted content, model configuration, and other business tables) and validates every copied table's row count and SHA-256 checksum. It excludes the Alembic version table and local maintenance markers, because those belong to the destination's schema/maintenance state. Table count follows the checked-out schema; it is not hard-coded.

It does **not** move `checkpoints.db`, LanceDB, actual uploaded attachments/covers, exports, `.env`, or `.key`. Preserve the **entire data directory**, including hidden files. Losing `.key` prevents decryption of stored model credentials. A different directory requires copying its contents while the app is stopped.

Choose a checkpoint policy explicitly:

- **Keep SQLite checkpoints:** leave `OPENFIC_CHECKPOINT_DATABASE_URL` unset and retain the original data directory. This preserves graph state while business data moves to PostgreSQL. This is the appropriate path if existing sessions need their previous checkpoints.
- **Start new PostgreSQL checkpoints:** provision an empty dedicated checkpoint database and set its URL only at cutover. Finish or cancel active/paused Agent runs first. Business messages/revisions remain readable, but old graph checkpoints and checkpoint-based resume/rollback do not transfer. Start new Agent tasks after cutover. There is no SQLite-checkpoint converter in this feature.

Stop all writers for the entire operation: desktop/server processes, background workers, and scheduled jobs. Do not start the target app before migration: startup seeds data and the target must be empty.

## 1. Back up and upgrade the source

Stop the old application. Record its version, data directory, database settings, and checkpoint choice. Make a verified offline copy of the whole directory to a new backup location before upgrading. Keep that copy with the old application version for rollback. For Docker volumes, stop the app and use your volume backup procedure; include both SQLite database files and any `-wal`/`-shm` files present, plus all other data files.

With the new source checkout installed, and still with no running application:

```bash
cd backend
uv sync --frozen
export OPENFIC_DATA_DIR='/absolute/path/to/existing-data'
export OPENFIC_DATABASE_URL="sqlite+aiosqlite:///$OPENFIC_DATA_DIR/openfic.db"
uv run --frozen openfic upgrade-database
```

Setting the source URL explicitly overrides any stale URL in `.env`. The command runs Alembic only, without workers or startup cleanup. Back up this upgraded directory too. Upstream SQLite schemas through `1022` are upgraded through `1023` (pinyin columns/backfill) and `1024` (PostgreSQL revision/task foreign key).

**Earlier private POC databases:** the old experimental branch also used revision numbers `1022`/`1023` for different operations. Those databases are not interchangeable with upstream `1022`. Do not use `alembic stamp` to force them into this chain. Restore the pre-POC SQLite backup and migrate from the supported upstream chain; if no such backup exists, inspect and reconcile its actual schema before using this procedure.

## 2. Provision an empty target

Create a dedicated PostgreSQL business database owned by the application role, with no app connected to it. If opting into PostgreSQL checkpoints, create a separate empty checkpoint database too. See the deployment guide for provisioning, TLS, and URL encoding.

Use a separate exported variable for the migration destination so the running configuration cannot be switched accidentally:

```bash
export OPENFIC_MIGRATION_TARGET_URL='postgresql+psycopg://openfic:URL_ENCODED_PASSWORD@db-host:5432/openfic_app'
```

The target must have no tables, or contain the **current**, structurally matching Alembic schema with all business tables empty. Nonempty or incompatible targets are rejected before schema changes. Do not point at unrelated databases or a checkpoint database. The migration role needs DDL and DML privileges; creating the database itself is an administrator operation.

## 3. Preflight without writes

```bash
uv run --frozen openfic migrate-sqlite-to-postgres \
  --source "$OPENFIC_DATA_DIR/openfic.db" \
  --target-url-env OPENFIC_MIGRATION_TARGET_URL
```

Expect `validated N rows across T tables`. This checks source integrity, foreign keys and the current Alembic head, target connectivity/emptiness/schema compatibility, and computes source counts/checksums. It does not create target tables or copy rows. This is a preflight, not proof that every target constraint will accept every row; apply verifies the actual copy.

## 4. Copy and verify

Keep both source and target applications stopped:

```bash
uv run --frozen openfic migrate-sqlite-to-postgres \
  --source "$OPENFIC_DATA_DIR/openfic.db" \
  --target-url-env OPENFIC_MIGRATION_TARGET_URL \
  --batch-size 1000 \
  --apply
```

Expect `migrated N rows across T tables; deferred foreign keys: K`. The source is opened read-only with a consistent read transaction. The target schema is prepared with Alembic. Rows are inserted in dependency order; nullable cyclic foreign keys are temporarily cleared and restored inside one data transaction. Counts and deterministic SHA-256 checksums (including binary, JSON and UTC-normalized timestamps) must agree before commit. A failure rolls back **all copied rows**. Schema creation is a separate transaction and may remain; after fixing the cause an empty, matching target can be retried. A successful migration cannot be blindly rerun against its populated target.

`--batch-size` controls insert batches, not total memory use: current verification loads tables into memory. Rehearse large databases on a backup and provision memory for the largest tables/checksum copies. Keep the source stopped until cutover; this tool has no incremental catch-up or dual-write mode.

## 5. Cut over and accept

Set `OPENFIC_DATABASE_URL` to the verified destination URL in the actual service environment. Keep `OPENFIC_DATA_DIR` unchanged or point to its complete copied directory. Keep the SQLite checkpoint URL unset, or explicitly set the fresh PostgreSQL checkpoint URL according to the checkpoint policy chosen above. Remove conflicting persistent `.env` entries. Then start exactly one instance:

```bash
export OPENFIC_DATABASE_URL="$OPENFIC_MIGRATION_TARGET_URL"
# If preserving SQLite checkpoints, remove this variable from both environment and .env.
unset OPENFIC_CHECKPOINT_DATABASE_URL
uv run --frozen openfic serve
```

For PostgreSQL checkpoints, replace the `unset` with the PostgreSQL URL from the deployment guide. Follow its acceptance checklist: health, project/chapter content, pinyin search, attachment text/files, audit totals, timezone dates, Agent state and restart persistence. Keep the source and backups untouched until acceptance finishes. Health endpoint: `/api/v1/health`.

## Docker commands for the same procedure

From the repository root, build the current checkout and stop `openfic`. Preserve the existing Compose project name so its `/data` volume stays the same. Export `OPENFIC_POSTGRES_PASSWORD` as described in the deployment guide; start only the database:

```bash
docker compose stop openfic
docker compose -f docker-compose.yml -f docker-compose.postgres.yml build openfic
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d postgres
# Back up /data before this upgrade command.
docker compose -f docker-compose.yml -f docker-compose.postgres.yml run --rm --no-deps \
  -e OPENFIC_DATABASE_URL=sqlite+aiosqlite:////data/openfic.db \
  -e OPENFIC_CHECKPOINT_DATABASE_URL= \
  openfic /app/.venv/bin/openfic upgrade-database
# No --apply: preflight only. The override supplies the target business URL.
docker compose -f docker-compose.yml -f docker-compose.postgres.yml run --rm --no-deps \
  openfic /app/.venv/bin/openfic migrate-sqlite-to-postgres --source /data/openfic.db
# Actual copy:
docker compose -f docker-compose.yml -f docker-compose.postgres.yml run --rm --no-deps \
  openfic /app/.venv/bin/openfic migrate-sqlite-to-postgres --source /data/openfic.db --apply
```

Before `up -d openfic`, finish acceptance preparation and select checkpoint policy. This override defaults to **fresh PostgreSQL checkpoints**; to preserve SQLite checkpoints, add a final Compose override setting `services.openfic.environment.OPENFIC_CHECKPOINT_DATABASE_URL` to `""`. Do not simply unset the host variable: the Compose file defines the URL itself. For example, save `compose.keep-sqlite-checkpoints.yml`:

```yaml
services:
  openfic:
    environment:
      OPENFIC_CHECKPOINT_DATABASE_URL: ""
```

Start the verified target and include the file in every later Compose command:

```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml \
  -f compose.keep-sqlite-checkpoints.yml up -d openfic
```

For fresh PostgreSQL checkpoints, omit that last override and run `docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d openfic`.

## Failure handling and rollback

| Situation | Action |
| --- | --- |
| Invalid driver, encoded password, connection/TLS/permissions failure | Fix deployment configuration; no fallback is performed. Re-run preflight. |
| Source is behind Alembic head | Back up, run `upgrade-database` against the source URL, and retry. Never bypass this with `stamp`. |
| Foreign-key/integrity failure | Repair a copy under review or restore a sound backup; the tool does not discard damaged rows. |
| Target is populated or incompatible | Use a fresh dedicated database. Do not erase existing data to make the check pass. |
| Apply or checksum failure | Data transaction rolled back; inspect the error, retain source, check empty target, fix and retry. |
| Before allowing writes on the target | Stop the new app, restore old application/configuration and its complete pre-upgrade directory backup. Restart with the original backend choice. |
| After users have written to the target | Stop writers and back up PostgreSQL plus current files first. Switching back to the old SQLite snapshot loses post-cutover changes. Reconcile/export those changes before rollback; no PostgreSQL→SQLite reverse migration is provided. |

Never run old and new installations concurrently against divergent copies. Do not delete SQLite files/backups or use `docker compose down -v` as a migration/rollback step.
