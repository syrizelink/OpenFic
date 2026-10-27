# 后台 Subagent 端到端测试

这套测试不需要真实模型 API key。Playwright 启动真实 OpenFic 后端、Vite 前端和 Chromium，通过界面发消息、审批、停止、重新打开任务及回滚。模型提供商指向测试服务内的 OpenAI-compatible HTTP 接口，由脚本控制工具调用、分片 SSE、响应内容、错误和完成顺序。

模型适配器、LangGraph、工具、权限钩子、Socket.IO、数据库迁移、检查点、请求队列及消息持久化均使用实际实现。测试除了检查页面，还读取真实数据库和运行任务注册表，断言每个请求的状态、结果、投递次数、修订与笔记变更，避免界面显示完成但仍有后台任务泄漏。

## 运行

先按项目开发文档安装后端依赖到 `backend/.venv`，安装前端依赖及 Playwright Chromium：

```bash
cd frontend
pnpm exec playwright install chromium
pnpm test:e2e:background
```

已有系统 Chromium 时可以指定路径，省略浏览器下载：

```bash
cd frontend
OPENFIC_E2E_CHROMIUM_PATH=/usr/bin/chromium pnpm test:e2e:background
```

默认使用前端 `19000`、后端 `19001`。可通过 `OPENFIC_E2E_FRONTEND_PORT` 和 `OPENFIC_E2E_BACKEND_PORT` 修改；占用端口会使测试启动失败，不复用已有服务。测试按单 worker、零自动重试运行，便于暴露生命周期和并发缺陷。

每次后端启动创建独立的 `openfic-e2e-subagents-*` 临时数据目录，不读取现有用户数据库、模型配置或密钥。所有模型请求都发到本地测试服务，使用无效占位 key。进程重启测试保留同一个临时目录，验证真实启动清理逻辑。

测试控制接口仅存在于 `backend/tests/e2e/background_server.py` 这个测试入口，不由生产应用注册。重启用例通过替换测试服务器进程模拟非正常退出，不调用生产关闭流程。

## 覆盖范围

可靠性修复专项通过 `pnpm test:e2e:reliability` 单独运行，覆盖同一通知调用跨轮次重放、跨轮次共享十个并发名额、释放名额后接纳替补、空闲通知的容量检查，以及看板提醒查询故障与恢复。其报告位于 `frontend/playwright-report/reliability/`。

| 范围 | 检查内容 |
| --- | --- |
| 非阻塞与兼容 | 后台派发立即返回，父代理继续执行独立工具；省略 `background` 或传 `false` 保持同步等待 |
| 完成顺序 | 瞬间完成、逆序完成、十个并发任务同时释放；每个请求独立投递且恰好一次 |
| 输入与容量 | 长 Unicode、换行及引号完整保存；第十一个派发拒绝，无幽灵任务；非法等待参数、未知代理、白名单限制、禁止嵌套派发 |
| 队列 | 运行中及空闲时通知沿用子会话和上下文；同步通知兼容；同批重复通知拒绝；回收后拒绝通知；请求序号、`request_id` 和结果一一对应 |
| 显式等待 | 零超时、短超时不取消后台任务；等待多个任务时任一完成即可返回；等待最新请求不误用旧结果；重复 ID 去重；不存在的会话返回错误 |
| 模型故障 | HTTP 503 重试恢复、HTTP 400、空内容、损坏 SSE；一个子代理失败不影响其他任务；父代理取得结果后的模型重试不重复报告；父模型错误后手动继续恢复后台结果 |
| 审批 | 后台子代理写笔记前停在真实审批；执行与拒绝分别验证实际数据库变更；父代理随后恢复；显式等待报告待审批；父取消后旧审批不能恢复子任务 |
| 取消与回收 | 父停止按钮取消整棵任务树；单独取消子任务不影响其他任务；重复取消；取消与完成竞态；回收不再投递旧结果 |
| 用户交互 | 后台等待时的新用户消息及时唤醒父代理；停止后新轮次不会复活旧请求 |
| 恢复 | 运行中刷新、完成后重新打开、浏览器离线期间完成后恢复、两个标签页观察同一会话 |
| 隔离与回滚 | 不同父会话不能取消彼此子任务；回滚撤销子代理已经审批的写入、后台报告及关联轮次 |
| 进程故障 | 实际重启服务，将遗留请求标记为取消；历史仍在；旧任务不自动重跑；新轮次继续工作 |
| 清理与可观测性 | 每例检查无未捕获浏览器异常、无意外模型调用、无遗留运行任务、无检查点清理错误 |

此外，后端测试直接验证检查点并发清理与写入互斥、清理被取消后事务回滚，以及子任务不继承父工具的 LangChain 审批上下文。

## 结果与调试

- HTML 报告：`frontend/playwright-report/background/index.html`，可运行 `pnpm exec playwright show-report playwright-report/background` 查看。
- 每例报告附有 `scenario-state` JSON，包含实际请求、消息、模型输入、数据库状态与运行状态。
- `browser-diagnostics` 附件保留浏览器 warning/error 输出；模型错误和离线测试会产生预期的错误日志。测试另外断言没有未捕获脚本异常或页面崩溃。Vite 开发模式还会输出 `ResizeObserver loop completed with undelivered notifications`，本套测试未将该布局观察器通知作为失败条件。
- 失败时保留截图、页面快照与 trace：`frontend/test-results/background/`。
- 后端日志：`/tmp/openfic-e2e-server-19001.log`，修改后端端口后文件名跟随变化。

只跑某类场景，或重复验证竞态：

```bash
pnpm test:e2e:background --grep '审批|离线|进程崩溃'
pnpm test:e2e:background --grep '同时发生|逆序|十个' --repeat-each=3
```

## 验证边界

这套测试验证确定的模型输出经过完整产品链路后的行为。它不验证真实模型是否会主动选择后台派发、遵循提示词或生成有用的创作内容；这些需要另行使用实际模型测试。当前浏览器环境为 Chromium，数据库为 SQLite，不代表 PostgreSQL、其他浏览器、桌面打包或跨机器网络的验证结果。服务重启的预期是取消遗留工作，不能据此宣称支持跨进程持续执行。

## 测试发现并修复的问题

1. **并发检查点清理冲突**：多个子代理共用 SQLite saver 连接，清理事务会与其他清理或检查点写入交错。改为使用 saver 自身的锁；取消时也回滚事务，防止遗留打开的事务。
2. **子代理跳过审批**：异步任务继承父工具的 LangChain 上下文，其中包含跳过工具预处理的状态。子代理现在使用独立的 context，正常执行自己的审批钩子。
3. **审批面板消失**：打开等待审批的子会话时，旧的 node/tool 实时事件重放覆盖了持久化审批状态。子代理暂停后清除该轮旧事件，再发出审批通知。
4. **后台审批接口阻塞**：父轮次仍 active 时，条件更新虽未命中，仍持有 SQLite 写事务，阻塞另一连接更新任务状态。启动子代理恢复前释放该事务。
5. **断线期间完成的结果没有回到界面**：已结束的流不在重放缓冲区中。Socket 重连及浏览器恢复联网时，从实际会话状态和任务历史恢复，并检查会话代次，防止覆盖已经切换或重启的会话。

## 本次验证记录（2026-10-22）

环境：Python 3.12.14、Node.js 24.19.0、Playwright 1.62.1、Chromium 151.0.7922.173、SQLite。未使用真实模型 API key。

| 检查 | 最终结果 |
| --- | --- |
| 后台 Subagent 浏览器完整套件 | **44 通过**，0 失败、0 跳过、0 flaky，零自动重试，约 10.6 分钟 |
| 重点并发与取消竞态重复验证 | 逆序完成、十任务并发、取消/完成竞态各 3 遍，**9 次全部通过**，零自动重试，约 2.8 分钟 |
| Agent runtime、Agent API 与迁移回归 | **1127 通过，8 跳过**，约 131 秒 |
| 前端全项目 `oxlint --type-aware --type-check` | 通过 |
| E2E 与 Node 配置的 TypeScript 检查 | 通过 |
| 修改的 Python 文件 Ruff 检查、`git diff --check` | 通过 |

8 个跳过项是 PostgreSQL 检查点清理测试，当前未配置 `OPENFIC_TEST_CHECKPOINT_DATABASE_URL`。本次浏览器结果指独立的后台 Subagent 套件，不包含原有 `pnpm test:e2e` 入口下的 9 个用例。

完整套件的 HTML 报告保存在 `frontend/playwright-report/background/`，竞态重复验证的 JUnit 结果保存在 `frontend/test-results/background-races/results.xml`。后者使用独立输出目录，不覆盖完整套件报告：

```bash
cd frontend
PLAYWRIGHT_JUNIT_OUTPUT_FILE=test-results/background-races/results.xml pnpm test:e2e:background --grep '同时发生|逆序|十个' --repeat-each=3 --reporter=list,junit --output=test-results/background-races
```

后端回归复现命令：

```bash
cd backend
.venv/bin/pytest -q tests/agent_runtime tests/api/test_agent.py tests/api/test_agent_resume_transactions.py tests/storage/test_background_subagents_migration.py
```

## 可靠性修复验证记录（2026-10-27）

未使用真实模型 API key，浏览器环境为 Chromium，数据库为 SQLite。

| 检查 | 结果 |
| --- | --- |
| 新增可靠性后端专项 | 19 通过，覆盖重复与不同通知并发、提交前后故障恢复、混合派发/唤醒争用名额、审批与取消清理占用 |
| 新增可靠性浏览器专项 | 4 通过，零自动重试，约 1.7 分钟 |
| Agent Board 浏览器完整套件 | 8 通过，零自动重试，约 3.5 分钟 |
| 后端整库首次运行 | 2392 通过、7 失败、19 跳过，约 246 秒 |
| 后端失败项复测 | 7 通过，约 59 秒；更新了工具权限清单与迁移头版本断言，并将 UV 缓存放到可写临时目录 |
| 原后台 Subagent 浏览器完整套件 | 43 通过、1 失败；失败为取消与完成同时发生的竞态 |
| 取消/完成竞态单独重复 | 14 次通过；其中 10 次附加临时事务跟踪，未重现首次锁异常 |
| Ruff、后端类型检查、前端格式与类型检查、E2E/Node TypeScript、差异空白检查 | 通过 |

后端整库首次运行的四项子进程失败来自只读的默认 UV 缓存目录；另外三项是此前新增工具与迁移之后未更新的测试断言。修正后对这七项逐一重测通过。整库其余 2392 项没有在这次复测中重复运行。

取消/完成竞态仍有一次未定位的 SQLite `database is locked` 异常，导致子请求进入 `error`，不能将该场景报告为稳定通过。后续 14 次通过不构成对首次异常的修复证明。失败 trace 保存在 `frontend/test-results/background/` 对应的取消/完成场景目录中。

复测子进程测试时，受限环境可使用：

```bash
cd backend
UV_CACHE_DIR=/tmp/openfic-uv-cache UV_NO_SYNC=1 .venv/bin/pytest -q --lf
```

`UV_NO_SYNC=1` 使用已经安装好的项目环境；正常开发环境应先完成依赖安装。19 个跳过项的具体条件由测试自身定义，不表示 PostgreSQL 或其他可选环境已经得到验证。
