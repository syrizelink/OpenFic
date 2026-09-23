# 首次部署与数据库选择

[English](database-deployment.en.md) · [迁移与回退](database-migration.zh-CN.md)

本手册适用于包含该特性的源码版本。旧版已发布安装包/镜像不一定包含该功能。当前尚未发布的修改请使用本工作区执行 `uv sync --frozen`，或构建其 Dockerfile；迁移命令与运行服务必须使用同一应用版本。

## 首次启动前选择

| 业务数据 | Agent Checkpoint | 配置 | 典型用途 |
| --- | --- | --- | --- |
| SQLite | SQLite | 两个变量均不设置 | 默认桌面版或单实例本地部署 |
| PostgreSQL | PostgreSQL | 两个变量均设置 | 自托管并独立管理关系型存储 |
| PostgreSQL | SQLite | 仅设置 `OPENFIC_DATABASE_URL` | 迁移业务数据、保留本地 Agent 历史 |
| SQLite | PostgreSQL | 仅设置 `OPENFIC_CHECKPOINT_DATABASE_URL` | 业务数据保留本地，独立存储 Checkpoint |

数据库选择不会自动实现多用户隔离、多副本或分布式 Worker，仍请运行单个应用实例。LanceDB、上传文件、导出文件、配置和加密密钥在所有模式下都保存在 `OPENFIC_DATA_DIR` 中；使用 PostgreSQL 仍需要持久化该目录。对外部署应配置访问控制，可使用现有 `OPENFIC_AUTH_PASSWORD`。

数据库在进程启动时选择。修改 URL 只是连接另一数据库，**不会搬运已有数据**。切换前停止应用；已有数据请按迁移手册操作。错误的协议/驱动会报错，PostgreSQL 连接失败也不会静默回退到 SQLite。

## 方案 A：SQLite（默认）

无需 PostgreSQL 服务。保持 `OPENFIC_DATABASE_URL` 和 `OPENFIC_CHECKPOINT_DATABASE_URL` 未设置，空值也采用默认配置。需要同时清理服务环境和数据目录 `.env` 中遗留的配置。

Docker 保持现有默认用法：

```bash
docker compose up -d
```

若要运行本次源码而非发布镜像：

```bash
docker build -t openfic:local .
docker run -d --name openfic -p 127.0.0.1:8000:8000 -v openfic:/data openfic:local
```

源码部署需要 Python 3.12 或 3.13 和 uv：

```bash
cd backend
uv sync --frozen
export OPENFIC_DATA_DIR="$HOME/.openfic"
uv run --frozen openfic upgrade-database
uv run --frozen openfic serve
```

`upgrade-database` 仅升级业务数据库结构，不启动服务、初始化种子数据或后台任务；启动服务时也会自动执行结构升级。CLI 默认目录为 `~/.openfic`，Docker 为 `/data`，直接使用 `uvicorn app.main:app` 时默认是 `backend/data`。建议显式设置 `OPENFIC_DATA_DIR`，避免打开错误的数据目录。

## 方案 B：使用 Docker Compose 部署 PostgreSQL

**全新部署**时，在仓库根目录运行：

```bash
# 生成可直接放入 URL 的密码；保存到部署密钥管理中，后续命令需复用。
export OPENFIC_POSTGRES_PASSWORD="$(openssl rand -hex 24)"
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

覆盖配置会构建当前源码、启用两个数据库 URL、启动 PostgreSQL 17，并创建 `openfic_app` 和 `openfic_checkpoint`。数据库不向宿主机发布端口。业务数据与 Checkpoint 存在 PostgreSQL 卷，`/data` 使用独立卷，两者都需要备份。

初始化 SQL 仅在新 PostgreSQL 数据卷上执行。修改密码环境变量不会更改已有数据库角色的密码。复用旧卷时，应显式创建 Checkpoint 数据库并配置凭证，不要通过删除数据卷解决。使用托管数据库时，分别创建业务库/Checkpoint 库，让应用角色拥有其 schema 并具备启动时建表、索引迁移权限，直接配置 URL，不启动内置数据库服务。

已有 SQLite 部署不要直接执行上述命令期待自动迁移，请先看[迁移手册](database-migration.zh-CN.md)。

## 方案 C：源码/安装包连接已有 PostgreSQL

创建两个空的专用数据库，所有者为应用角色。由有权限的 PostgreSQL 管理员执行示例：

```bash
createdb -O openfic openfic_app
createdb -O openfic openfic_checkpoint
```

按上文安装当前源码，然后在应用服务环境中设置：

```bash
export OPENFIC_DATA_DIR='/absolute/path/to/openfic-data'
export OPENFIC_DATABASE_URL='postgresql+psycopg://openfic:URL_ENCODED_PASSWORD@db-host:5432/openfic_app'
export OPENFIC_CHECKPOINT_DATABASE_URL='postgresql://openfic:URL_ENCODED_PASSWORD@db-host:5432/openfic_checkpoint'
uv run --frozen openfic upgrade-database
uv run --frozen openfic serve --host 0.0.0.0
```

替换示例中的占位符。用户名/密码中的特殊字符需要 URL 编码，例如 `@` → `%40`、`%` → `%25`；真实凭证保存在受限环境文件或密钥管理系统中。两个 URL 均支持 `postgresql://`、`postgresql+psycopg://`，也会规范化 `postgresql+psycopg_async://`。不支持其他 PostgreSQL 驱动。远程服务器可附加 Psycopg 连接参数，例如 `sslmode=verify-full&sslrootcert=/path/to/ca.pem`。数据库连接时区统一为 UTC。安装依赖包含驱动，但默认 SQLite 模式不会连接 PostgreSQL。

运行时也会读取 `OPENFIC_DATA_DIR/.env`，进程环境变量优先。迁移 CLI 的目标地址必须来自**已导出的进程环境变量**，不会从该 `.env` 读取。业务库和 Checkpoint 库应分开，以便独立管理和校验迁移。

## 验收与日常维护

1. 检查启动日志中迁移成功且没有连接或初始化错误。`curl --fail http://127.0.0.1:8000/api/v1/health` 只验证 HTTP 可用，不能单独证明持久化正常。
2. 新建项目、重命名、中文/拼音搜索，重启后再次打开。
3. 配置模型后执行 Agent 对话，重启后检查历史并继续新一轮，同时验证附件读取及版本回滚。
4. 检查仪表盘和指定时区的写作日期统计。
5. 停止应用后，将业务库、Checkpoint 库和**含 `.key` 的完整数据目录**作为同一时间点备份。PostgreSQL 使用 `pg_dump -Fc` / `pg_restore`；SQLite 使用一致性备份或停机后复制完整目录。

自动验证范围与限制见 [database-validation.md](database-validation.md)。真实模型调用和生产恢复演练仍需在部署环境验收。当前测试基线为 PostgreSQL 17，不据此声称其他大版本已通过验证。
