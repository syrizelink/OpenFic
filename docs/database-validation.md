# Database change review and validation / 数据库修改审查与验证

Reviewed against upstream `main` commit `27a565f` (OpenFic 0.11.1), with the local optional PostgreSQL changes. Results below were produced on 2026-09-23 using Python 3.12 and an isolated PostgreSQL 17 instance. They replace earlier POC results; no production database was used.

本次基于上游 `main` 的 `27a565f` 审查本地 PostgreSQL 可选部署修改；以下为 2026-09-23 在 Python 3.12 与独立 PostgreSQL 17 上得到的结果，不沿用旧 POC 的测试结论，也未使用生产数据库。

## Review findings addressed / 已处理的问题

| Impact | Finding and resolution / 问题及修复 |
| --- | --- |
| P1 | Local Alembic `1022` conflicted with upstream attachment migration. Preserve upstream `1022`, move local pinyin/FK migrations to `1023` → `1024`, and test upgrades from both `1021` and `1022`. / 保留上游附件迁移，重新衔接本地迁移链。 |
| P1 | The migration applied target DDL before checking for existing data. Preflight now rejects populated/incompatible targets before DDL, and verifies copied data before commit. / 目标库先预检，再建表；校验失败回滚全部复制数据。 |
| P2 | Global SQLite PRAGMA hooks affected the read-only migration source and unrelated engines. Scope the hook to the application's SQLite engine; test a read-only source in DELETE journal mode. / SQLite 连接调优仅作用于业务引擎，源库使用只读一致性事务。 |
| P2 | Invalid checkpoint URLs silently selected SQLite; plain PostgreSQL business URLs could select the wrong driver. Validate and normalize supported URLs, retain explicit mixed modes, and hide credentials from settings representations/errors. / 配置错误明确报错，避免静默回退。 |
| P2 | Percent-encoded credentials conflicted with Alembic ConfigParser interpolation. Escape percent signs and test migration using an encoded password. / 修复 URL 编码密码的 Alembic 兼容性。 |
| P2 | Failed PostgreSQL saver setup left a cached half-initialized instance/connection. Close it and publish the singleton only after successful setup; test retry. / 初始化失败释放连接，成功后才缓存。 |
| P2 | The original test script assumed pre-created shared databases and could delete fixed IDs. PostgreSQL tests now create uniquely named databases, migrate them, and drop only their own databases. / 集成测试使用独立临时库。 |

Deployment selection remains optional: no URLs means SQLite for both stores. PostgreSQL does not turn the app into a multi-replica/multi-user service. The packaged driver dependencies are included in both modes; database connection selection is made at startup.

部署选择保持可选：不设置 URL 时两种存储均使用 SQLite。驱动依赖包含在安装中，但仅在选择 PostgreSQL 时连接它；不据此声明多副本、多用户能力。

## Automated checks / 自动验证

- Full backend regression **including PostgreSQL integration: 1799 passed**, 64.90 seconds.
- `uv run --frozen ruff check .`: passed.
- `uv run --frozen ty check app`: passed.
- `uv lock --check --offline`: passed.
- PostgreSQL Alembic metadata comparison (`command.check`) is part of the integration test and passed.
- `git diff --check`, YAML parsing and documentation link checks: passed.

Key assertions include default/mixed configuration, invalid schemes and credential redaction, source upgrade/backfill, unique migration head, current text attachments with null dimensions, binary blobs, cyclic foreign keys, dry-run leaving an empty target untouched, refusal of nonempty/incompatible targets, full transaction rollback on checksum mismatch, unchanged source bytes, pinyin rename/search, idempotent content blobs, checkpoint writes/restore/pruning/rollback deletion/blob cleanup, and UTC/Shanghai/New York aggregation under a non-UTC server default.

覆盖默认与混合配置、错误配置/凭证隐藏、旧库升级及拼音回填、迁移单 head、新版文本附件和空尺寸、二进制与循环外键、预检无写入、目标库拒绝规则、校验失败回滚、源文件不变、重命名后的拼音搜索、Checkpoint 清理与恢复，以及数据库默认非 UTC 时的多时区统计。

To reproduce from `backend`:

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ty check app
uv run --frozen pytest -q
```

Without PostgreSQL test configuration, its integration tests skip. To run them, use a **test server** and a role with CREATEDB permission. `OPENFIC_POSTGRES_TEST_URL` identifies the administration connection; fixtures create new randomly named business/checkpoint databases on that server and remove them afterward:

```bash
export OPENFIC_POSTGRES_TEST_URL='postgresql://TEST_ROLE:URL_ENCODED_PASSWORD@127.0.0.1:5432/postgres'
uv run --frozen pytest -q tests/integration
# Or run the entire suite, including PostgreSQL:
uv run --frozen pytest -q
```

CI now starts PostgreSQL 17 and runs this integration suite separately from the default SQLite regression. The GitHub-hosted run has not been executed from this local task.

CI 已配置 PostgreSQL 17 服务与独立集成测试步骤；本任务尚未触发远端 GitHub CI。

## Runtime smoke checks / 实际运行检查

Using temporary directories and disposable databases, all four combinations (SQLite/SQLite, PostgreSQL/PostgreSQL, PostgreSQL/SQLite, SQLite/PostgreSQL) were started through the real CLI. Checks covered health, startup maintenance reaching `ready`, project creation, pinyin search, process restart and retained project data. SQLite files were present only for stores configured to use SQLite. Background workers and external telemetry were disabled for this isolated smoke run.

四种组合均通过真实 CLI 启动，检查健康接口、启动维护达到 `ready`、创建项目、拼音搜索、重启及数据保留，并核实仅 SQLite 模式生成对应 SQLite 文件。该独立运行检查关闭了后台 Worker 和外部遥测。

## Boundaries / 未验证或不支持的范围

- No Docker executable is installed on this host: Compose/YAML was statically inspected; the container build/start itself was **not** run. / 本机无 Docker，未验证镜像构建与容器启动。
- No live model-provider calls, production migration, large-database benchmark, or production backup/restore drill was performed. / 未调用真实模型，未迁移生产库，未做大库性能或生产恢复演练。
- PostgreSQL 17 is the tested major version. / 测试基线为 PostgreSQL 17。
- Existing SQLite checkpoints are not converted. Keep SQLite checkpoints for old graph state, or start new Agent tasks with a fresh PostgreSQL checkpoint store. / 不转换旧 Checkpoint；保留原 SQLite 或切换后创建新任务。
- Earlier private POC migration IDs are incompatible with the new upstream chain; restore the pre-POC backup or reconcile the actual schema separately. / 旧私有 POC 数据库需单独处理。
- Migration insert batches are bounded, but checksum/table loading still scales with table size. No reverse migration or multi-instance guarantee is provided. / 插入分批，校验仍按表占用内存；无反向迁移及多实例保证。
