# SQLite → PostgreSQL 迁移与回退

[English](database-migration.en.md) · [首次部署](database-deployment.zh-CN.md)

这是业务数据库的停机单向迁移，不是实时同步。结构升级、数据复制和服务启动必须使用同一源码版本。命令不会自动修改运行时数据库配置。自动化测试不会修改生产数据库。

## 迁移范围与前提

工具复制当前业务结构中的项目、章节、消息、版本、附件元数据/提取文本、模型配置等表，并逐表校验行数与 SHA-256。排除 Alembic 版本表和本地维护标记，因为它们属于目标库自身的结构/维护状态。表数量随当前源码结构确定，不写死。

工具**不迁移** `checkpoints.db`、LanceDB、真实附件/封面、导出文件、`.env` 和 `.key`。必须保留**含隐藏文件的完整数据目录**；丢失 `.key` 将无法解密已有模型凭证。更换目录时，在应用停止期间复制完整内容。

明确选择 Checkpoint 策略：

- **保留 SQLite Checkpoint**：不设置 `OPENFIC_CHECKPOINT_DATABASE_URL`，继续使用原数据目录。业务库迁移后保留原图执行状态；已有会话还需要旧 Checkpoint 时采用此方案。
- **启用全新 PostgreSQL Checkpoint**：单独创建空库，在切换时设置 URL。先结束或取消所有运行中/暂停的 Agent。业务消息和版本仍可阅读，但旧图 Checkpoint 及依赖它的续跑/回滚不会迁移。切换后创建新的 Agent 任务。本特性没有 SQLite Checkpoint 转换器。

整个操作期间停止所有写入者：桌面/服务进程、后台 Worker 和定时任务。迁移前不要启动目标应用，其启动流程会写入种子数据，而迁移要求目标为空。

## 1. 备份并升级源库

停止旧应用，记录应用版本、数据目录、数据库配置和 Checkpoint 策略。在升级前，将完整目录离线复制到新的备份位置并验证可读，将其与旧版本应用配套保存用于回退。Docker 数据卷应在应用停止后按卷备份流程处理；包括两个 SQLite 文件、仍存在的 `-wal`/`-shm` 文件及所有其他数据。

安装新源码后，保持应用停止：

```bash
cd backend
uv sync --frozen
export OPENFIC_DATA_DIR='/absolute/path/to/existing-data'
export OPENFIC_DATABASE_URL="sqlite+aiosqlite:///$OPENFIC_DATA_DIR/openfic.db"
uv run --frozen openfic upgrade-database
```

显式源 URL 会覆盖 `.env` 中遗留的配置。命令只执行 Alembic，不启动 Worker 或启动清理任务。升级完成后再保存一份完整目录备份。上游 SQLite 至 `1022` 的结构会继续执行 `1023`（拼音字段与回填）和 `1024`（PostgreSQL 版本/任务外键）。

**旧私有 POC 数据库**：旧实验分支也曾用 `1022`/`1023` 编号表示其他操作，不能将其与上游 `1022` 混用。不要使用 `alembic stamp` 强行接入迁移链。应从 POC 前的 SQLite 备份恢复后走本流程；没有备份时，先检查实际结构并制定单独的修复方案。

## 2. 准备空目标库

创建应用角色拥有的专用 PostgreSQL 业务库，不连接运行中的应用。选择 PostgreSQL Checkpoint 时，再创建独立空库。建库、TLS 和 URL 编码见部署手册。

使用单独导出的变量保存迁移目标，避免提前切换运行配置：

```bash
export OPENFIC_MIGRATION_TARGET_URL='postgresql+psycopg://openfic:URL_ENCODED_PASSWORD@db-host:5432/openfic_app'
```

目标必须完全无表，或具有**当前** Alembic 版本、字段集合一致、业务表全空的结构。非空或不兼容目标会在结构修改之前被拒绝。不要指向无关数据库或 Checkpoint 库。迁移角色需要 DDL 和 DML 权限；数据库本身由管理员创建。

## 3. 只读预检

```bash
uv run --frozen openfic migrate-sqlite-to-postgres \
  --source "$OPENFIC_DATA_DIR/openfic.db" \
  --target-url-env OPENFIC_MIGRATION_TARGET_URL
```

预期输出 `validated N rows across T tables`。预检检查源库完整性、外键、当前 Alembic head、目标连通性/空库/结构兼容性，并计算源数据行数和校验和。不建目标表、不复制数据。预检不能证明所有数据满足目标约束，实际写入后的校验由下一步完成。

## 4. 复制与校验

保持源和目标应用均停止：

```bash
uv run --frozen openfic migrate-sqlite-to-postgres \
  --source "$OPENFIC_DATA_DIR/openfic.db" \
  --target-url-env OPENFIC_MIGRATION_TARGET_URL \
  --batch-size 1000 \
  --apply
```

预期输出 `migrated N rows across T tables; deferred foreign keys: K`。源库以只读方式打开并使用一致性读事务。工具通过 Alembic 准备目标结构，按依赖顺序复制；可空循环外键在同一数据事务内临时清空并恢复。提交前，行数和确定性 SHA-256 必须一致，包括二进制、JSON 及按 UTC 规范化的时间。失败会回滚**全部复制数据**。建表是独立事务，结构可能保留；修复原因后，结构一致的空目标可重试。成功后不能直接在已填充目标上重复执行。

`--batch-size` 仅控制插入批次，不限制整体内存：当前校验会把表载入内存。大库请先用备份演练，预留最大表及校验副本所需内存。源应用应一直停止到切换完成；工具不提供增量追平或双写。

## 5. 切换与验收

在实际服务环境中将 `OPENFIC_DATABASE_URL` 设为验证后的目标 URL。保持 `OPENFIC_DATA_DIR` 不变，或指向其完整副本。按前面策略保留 SQLite Checkpoint，或显式配置全新 PostgreSQL Checkpoint。清理持久化 `.env` 中冲突的值，然后只启动一个实例：

```bash
export OPENFIC_DATABASE_URL="$OPENFIC_MIGRATION_TARGET_URL"
# 保留 SQLite Checkpoint 时，同时从进程环境和 .env 中移除该变量。
unset OPENFIC_CHECKPOINT_DATABASE_URL
uv run --frozen openfic serve
```

选择 PostgreSQL Checkpoint 时，将 `unset` 换为部署手册中的 URL 设置。按部署手册检查健康接口、项目/章节正文、拼音搜索、附件文本与文件、审计统计、时区日期、Agent 状态和重启持久化。验收前保留源数据和备份。健康接口路径为 `/api/v1/health`。

## Docker 对应操作

在仓库根目录构建当前源码并停止 `openfic`。保持原 Compose 项目名，确保继续挂载同一个 `/data` 卷。按部署手册导出 `OPENFIC_POSTGRES_PASSWORD`，先只启动数据库：

```bash
docker compose stop openfic
docker compose -f docker-compose.yml -f docker-compose.postgres.yml build openfic
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d postgres
# 执行升级命令前备份 /data。
docker compose -f docker-compose.yml -f docker-compose.postgres.yml run --rm --no-deps \
  -e OPENFIC_DATABASE_URL=sqlite+aiosqlite:////data/openfic.db \
  -e OPENFIC_CHECKPOINT_DATABASE_URL= \
  openfic /app/.venv/bin/openfic upgrade-database
# 不加 --apply，仅预检。覆盖配置提供了目标业务库 URL。
docker compose -f docker-compose.yml -f docker-compose.postgres.yml run --rm --no-deps \
  openfic /app/.venv/bin/openfic migrate-sqlite-to-postgres --source /data/openfic.db
# 实际复制：
docker compose -f docker-compose.yml -f docker-compose.postgres.yml run --rm --no-deps \
  openfic /app/.venv/bin/openfic migrate-sqlite-to-postgres --source /data/openfic.db --apply
```

在执行 `up -d openfic` 前完成验收准备并决定 Checkpoint 策略。该覆盖配置默认启用**全新 PostgreSQL Checkpoint**；要保留 SQLite，请增加最后一层 Compose override，将 `services.openfic.environment.OPENFIC_CHECKPOINT_DATABASE_URL` 设为 `""`，并在后续所有 Compose 命令中使用。仅取消宿主机变量无效，因为 Compose 文件本身定义了该 URL。例如保存 `compose.keep-sqlite-checkpoints.yml`：

```yaml
services:
  openfic:
    environment:
      OPENFIC_CHECKPOINT_DATABASE_URL: ""
```

启动验证后的目标，后续 Compose 命令也带上此文件：

```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml \
  -f compose.keep-sqlite-checkpoints.yml up -d openfic
```

全新 PostgreSQL Checkpoint 则不添加最后一个覆盖文件，使用 `docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d openfic`。

## 失败处理与回退

| 情况 | 处理 |
| --- | --- |
| 驱动、密码编码、连接/TLS/权限错误 | 修正部署配置后重新预检，不会自动回退数据库。 |
| 源库版本落后 | 备份后针对源 URL 执行 `upgrade-database`；不要用 `stamp` 跳过。 |
| 外键或完整性错误 | 在副本上检查修复或恢复可靠备份，工具不会丢弃坏数据。 |
| 目标非空或不兼容 | 使用新的专用库，不要为了通过检查而清空已有数据。 |
| 写入或校验失败 | 数据事务已回滚；保留源库，检查空目标，修复原因后重试。 |
| 尚未允许用户写入目标 | 停止新应用，恢复旧应用、旧配置和升级前的完整目录备份，按原数据库选择启动。 |
| 用户已经写入目标 | 先停止写入并备份 PostgreSQL 与当前文件。直接切回旧 SQLite 会丢失切换后的修改；先导出/核对增量再回退。本工具不提供 PostgreSQL→SQLite 反向迁移。 |

不要同时运行指向分叉数据副本的新旧实例。不要把删除 SQLite 文件/备份或 `docker compose down -v` 当作迁移或回退步骤。
