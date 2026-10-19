# 插件改造对原有功能的历史回归验证

验证日期：2026-10-19；修复提交：`ce7383e`。所有测试使用隔离数据目录。

此记录对应移除 Claude Mods 兼容支持之前的版本，保留原始结果。当前代码已移除专用适配、依赖和用例，最新验证见 [移除验证记录](./plugin-native-verification.md)。

验证范围是从 `9dad03b` 到 `e6217b0` 的整轮 SDK、Mods 和 UI 改造，以及本次发现问题后的修复。该轮有 113 个文件变化，其中 30 个为已有文件。重点审查 Agent 编排、子 Agent、工具注册与审批、上下文转换、应用中间件，以及编辑器、全局布局、设置和仪表盘中的接入点。

## 发现并修复的问题

| 问题 | 影响 | 修复与回归证据 |
| --- | --- | --- |
| 插件工具无条件加入显式工具列表 | `get_tools(names=[])` 仍返回插件工具；只选择内置工具的 Agent 也会获得额外工具 | 注册表严格按显式名单过滤；默认 Build 显式加入插件工具，Plan/子 Agent 保留原有范围；添加启用插件时的名单对照测试 |
| 插件工具遗漏构建钩子 | 原有描述/配置定制不能作用于插件工具 | 插件工具与内置工具一致执行 build hooks，保留审批和结果钩子 |
| 观察型上下文钩子改变消息元数据 | 系统消息的 id/name/缓存元数据丢失；AI 用量、工具错误状态和 artifact 不能按原类型恢复 | 按原系统分区保留消息字段，并用具体 LangChain 消息类型恢复；测试系统消息、图片附件、工具调用关联、token 用量和错误状态逐字段不变 |
| 观察型工具钩子无法复制内置结构化结果 | `ToolResult` 是带 payload 的字符串子类，深复制时构造失败，导致章节读取和后续压缩异常 | 实现保留 payload 且不共享可变对象的深复制；加入 `tool.call`/`tool.result` 回归测试，并在启用插件后实际读取 15 章、压缩生成摘要，接口均成功 |
| `ui.context` 绕过编辑器读取声明 | 只有 `ui` 能力的插件也可获得当前正文 | 无 `editor.read` 时返回 `editor: null`；浏览器在真实章节和 UI-only iframe 中验证受限读取和写入拒绝 |
| 数据通知重建编辑器 | 启用插件后，自己的自动保存通知触发 working-copy 查询重载，Tiptap 重新挂载、撤销历史丢失 | 保留 working-copy/编辑器实例，仅更新远端实体数据，由已有远端更新保护逻辑处理；对无插件、停用、启用三种状态验证自动保存、撤销/重做、手动保存、跨章节切换和笔记保存 |

工具名单修复保留了默认 Build 使用插件工具的能力。其他 Agent 可通过定义的 `metadata.plugin_tools` 显式指定完整插件工具名，Build 也可通过空列表关闭；停用或卸载后的工具不会加入名单。此设置通过已有 Agent 定义 API 保存，不新增工具分类或改变内置分类的含义。

## 验证矩阵

| 范围 | 执行方式 | 结果 |
| --- | --- | --- |
| 全部后端功能 | pytest 全量，包含分支覆盖率与 JUnit | 2323 passed、19 skipped，424.56 秒；18 项跳过在 PostgreSQL 专项补测通过，剩余 Windows Proactor |
| PostgreSQL 检查点、事务、迁移、跨数据库仓库 | 临时 PostgreSQL 17 + pgvector；原模块及 SQLite 对照 | 134 passed；此前 18 项 PostgreSQL 条件跳过全部实际通过 |
| 原有 Agent 浏览器流程 | 审批恢复、取消后拒绝旧审批、取消后新消息、运行取消、消息排队、手动压缩、压缩取消、提问面板 | 8 个场景通过，启用透传观察插件执行；排队时序修正及复验见下文 |
| 仪表盘 | 原有大数据详情按需加载及统计切换用例 | 1 passed |
| 章节与笔记 | 无插件、停用、启用三种状态，真实 API、数据库与 Tiptap | 3 passed；包含权限、保存、撤销/重做和切换检查 |
| 原插件和新增扩展 | 项目统计、三个示例、React SDK、TSX Mod、官方 Mods、声明式/iframe 混合 | 6 passed，生产静态构建执行，不在测试期间重新构建静态目录 |
| 全局入口 | 项目、世界书、角色、提示词链、仪表盘、设置插件分类、移动端布局 | 1 passed，生产静态构建 |
| 桌面数据管理 | 原有 archive 和 data-manager 测试，直接运行两份测试文件 | 5 + 7 = 12 passed |
| 静态检查与构建 | 后端 Ruff/ty，前端格式/lint/类型/E2E 类型，桌面主进程与 renderer 类型/lint，前端及桌面 setup 构建 | 最终检查记录见证据文件 |

最终 19 个不同的浏览器场景均取得通过结果。完整结果与覆盖率保存在同目录的 [plugin-regression-results.json](./plugin-regression-results.json)。原始日志、JUnit、覆盖率 JSON 和隔离测试数据保存在 `/workspace/openfic-verification/2026-10-19/`。覆盖率来自后端 pytest，不包含独立服务中的浏览器执行，不能解读为所有行为都已覆盖。

后端整体行覆盖率为 79.05%，分支覆盖率为 59.73%（coverage.py 综合指标 75.00%）。以下为主要接入点的独立 pytest 覆盖率，浏览器服务执行未合并进来：

| 文件 | 行 | 分支 |
| --- | --- | --- |
| `context/processors/to_langchain.py` | 100.00% | 100.00% |
| `tools/registry.py` | 100.00% | 100.00% |
| `tools/base.py` | 90.26% | 70.31% |
| `graph/react_agent.py` | 88.10% | 77.07% |
| `graph/orchestrator/graph.py` | 86.92% | 55.56% |
| `runner/subagent_runner.py` | 83.06% | 63.44% |
| `plugins/runtime.py` | 82.11% | 68.09% |
| `api/routers/agent_runtime.py` | 56.00% | 31.44% |
| `main.py` | 55.77% | 24.49% |

原有 API 和应用入口仍有未覆盖分支；本次通过真实浏览器补充关键流程验证，不能据此保证所有异常和平台分支均无问题。后端通过用例中，Agent Runtime 为 980 项、API 为 695 项、插件为 62 项、存储为 135 项，其余覆盖模型、后台任务、检索、Socket、宏、CLI 等模块。

## 已有文件的验证对应

| 已有接入点 | 验证内容 |
| --- | --- |
| `context/processors/to_langchain.py`、`graph/react_agent.py`、`graph/orchestrator/graph.py` | 原有上下文、工具调用与 Graph 测试；启用透传插件后的消息元数据逐字段比较、实际审批与压缩 |
| `runner/subagent_runner.py`、`tools/base.py`、`tools/registry.py` | 子 Agent 运行、工具构建/执行钩子、工具分类和显式名单、错误结果、嵌套工具审批及调用关联 |
| `api/routers/agent_runtime.py`、`main.py` | 原有 Agent API、认证、入口、锁、取消、排队、审批恢复与提问用例；浏览器通过真实 Socket 和数据库驱动 UI |
| 原有插件 API、host、manifest、Python/JS SDK | 生命周期、失败回滚、安装包校验、认证、资源票据、能力检查、CRUD、事件、OAuth、网络和存储；真实管理 UI 安装/配置/更新/停用/卸载 |
| `app-layout.tsx`、`status-bar.tsx`、`projects-page.tsx`、`settings-content.tsx` | 原有页面导航、状态栏/侧栏、插件管理分类、移动端布局，以及项目统计插件入口 |
| `agent-input.tsx`、`writing-page.tsx` | 发送、取消、排队、审批与提问面板；Mod 原位显示；三个示例在真实会话中的工具、Graph 和提示词行为 |
| `chapter-editor.tsx`、`note-editor.tsx` | 三种插件状态下的手动编辑、自动/手动保存、撤销/重做、章节/笔记切换与重载；真实 iframe SDK 读取权限和插入保存 |
| `dashboard-page.tsx` | 原有按需详情加载、统计切换用例；真实后端的仪表盘导航 |
| `pyproject.toml`、`uv.lock`、插件页面/插槽/CSS | 后端全量与类型检查；前端生产构建、React/Mods/声明式和 iframe 混合渲染；wheel 内嵌资源逐字节核对 |

一次并行运行曾触发两条原有并发取消测试的共享 `AsyncSession` 异常；单独复查两项均通过，最终全量改为独立执行。浏览器取消和排队测试的仿真提供商原先返回过快，可能在读取任务元数据或输入第二条消息期间进入审批面板；仅为这些场景延长仿真响应等待时间，未改动对应流程的应用代码或用例断言。中止批次保留在 `backend-contended.log`、`browser-contended.log`，不计入最终通过数。

核心浏览器批次先得到 11 passed、1 failed（排队）；修正提供商时序后，排队单项复验通过。原批次 JUnit 保存在 `browser-core-before-queue-fix.xml`，复验为 `browser-queue.xml`，按同名场景的最终结果统计为 12 项通过，不把早期失败记录删除或计作通过。

## 单独确认的原有问题

在浏览器回归中，取消正在进行的手动压缩可以释放运行状态、恢复后续对话，但被取消的压缩 HTTP 请求会返回 500（`No response returned`）。原有浏览器用例只检查状态恢复，没有断言这个请求的响应码。

2026-10-18 使用实际运行的 `9dad03b` 基线后端对照，结果同样为：取消请求 200、压缩请求 500、取消后 `is_running=false`。因此该问题不是本轮插件改造引入；本次将其保留为明确的原有问题，没有将取消场景的 UI 测试通过描述为接口完全无错误。

## 可复现方式

后端全量：

```bash
cd backend
uv run pytest --cov=app --cov-branch --cov-report=json:coverage.json --junitxml=results.xml -q -ra
```

原有功能和插件的浏览器验证使用专用的 `tests.plugins.regression_app`，只模拟 Google Drive 和模型提供商协议。应用、数据库、原生工具、审批、中断、队列、检查点与 UI 均走真实实现。仪表盘已有用例使用其原有的 API fixture；主应用导航测试使用真实后端。

```bash
# 终端一：必须使用可删除的独立数据目录。
cd backend
OPENFIC_DATA_DIR=/tmp/openfic-regression-data OPENFIC_AUTH_PASSWORD= \
  uv run uvicorn tests.plugins.regression_app:app --host 127.0.0.1 --port 8021

# 服务就绪后创建项目、测试模型，并启用透传观察插件。
uv run python tests/plugins/prepare_regression.py \
  --backend http://127.0.0.1:8021 --observer --output /tmp/regression-seed.json

# 终端二：开发预览供原有 dashboard fixture/编辑器桥接检查使用。
cd frontend
VITE_BACKEND_URL=http://127.0.0.1:8021 pnpm dev --port 9020

# 另一个终端：先构建，再启动生产静态预览；测试期间不要重建。
pnpm build
OPENFIC_E2E_BACKEND=http://127.0.0.1:8021 OPENFIC_E2E_PREVIEW_PORT=9022 \
  node e2e/serve-plugin-preview.mjs

# 串行运行，避免各套件对模型设置和插件状态互相干扰。
OPENFIC_E2E_BASE_URL=http://127.0.0.1:9020 \
OPENFIC_E2E_PLUGIN_BASE_URL=http://127.0.0.1:9022 \
OPENFIC_E2E_BACKEND=http://127.0.0.1:8021 \
  node e2e/run-plugin-regression.mjs /tmp/regression-seed.json

OPENFIC_E2E_BASE_URL=http://127.0.0.1:9022 pnpm exec playwright test e2e/app-shell-regression.spec.ts
```

系统 Chromium 可通过 `OPENFIC_E2E_CHROMIUM_PATH` 指定；原有录像测试还需要 Playwright ffmpeg。PostgreSQL 测试使用独立可删除数据库，按原测试的 `OPENFIC_TEST_DATABASE_URL` 与 `OPENFIC_TEST_CHECKPOINT_DATABASE_URL` 配置执行。

PostgreSQL 专项（先配置上述两个数据库变量）：

```bash
cd backend
uv run pytest -q -ra \
  tests/agent_runtime/test_checkpointer.py \
  tests/api/test_project_transactions.py \
  tests/storage/test_attachment_mime_migration.py \
  tests/storage/test_dashboard_metadata_indexes.py \
  tests/storage/test_database_backend.py \
  tests/storage/test_database_migration.py \
  tests/storage/test_cross_database_repositories.py
```

桌面测试直接执行文件，确保运行其中全部子用例：

```bash
cd desktop
pnpm type-check
pnpm lint
node tests/main/archive.test.mjs
node tests/main/data-manager.test.mjs
pnpm build:setup
pnpm build:main
```

wheel 在隔离打包目录复用已通过构建的前端产物；核对 29 个变化的后端文件和 740 个前端资源逐字节一致。没有在运行中的静态预览目录上重新构建。另核对 SDK npm 包、两份 SDK 声明和四个示例 ZIP 与各自源码一致。

## 覆盖边界

不包含真实 Google 账户、真实付费模型、Windows Proactor、macOS/Windows 原生桌面安装及真实隧道服务。模型协议仿真验证执行链与状态，不评价实际模型的推理质量。第三方插件仍可主动改变流程；本次验证包含无插件、停用以及启用透传插件/所提供示例的行为，不能保证任意第三方插件均无副作用。
