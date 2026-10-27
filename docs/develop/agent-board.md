# Agent Board：代理直接共享原始信息

同一个任务的主 Agent 和子 Agent 共享一块持久化看板。Agent 使用 `board_post` 发布发现、证据、问题、结论或阻塞，其他 Agent 使用 `board_read` 读取原文，减少主 Agent 转述导致的信息偏差。同步与后台子 Agent 均可使用。

助手顶部的 **Agent Board** 按钮打开查看面板，展示参与者、消息类型、发送者、收件人、时间、回复关系及回滚撤回状态。支持实时更新、刷新、重新打开和加载更早消息。面板仅供查看，打开面板不算 Agent 已读。

## 工具与协作方式

`board_read` 默认读取最早的 20 条有效消息，可指定 `limit: 1..50`。返回当前代理身份 `self`、参与者列表、消息及增量 `cursor`。后续读取传入上一次返回的 `cursor`；`has_more` 表示还有消息。游标只适用于当前任务，不是消息 ID。

```json
{"limit":20}
```

`board_post` 的发送者身份由运行时决定，不能由模型指定。收件人是 `main`、`ALL` 或 `board_read` 返回的子 Agent `dispatch_id`；不能发给自己或其他任务的代理。

```json
{"to":"ALL","type":"INFO","body":"第 3 章第 42 行记载阿青十九岁；第 4 章跨年后应为二十岁。"}
```

类型包括 `INFO`（发现）、`ASK`（问题）、`RESULT`（结论）、`HOLD`（阻塞）和 `VETO`（异议）。更正结论、补充证据或解除阻塞时，通过 `reply_to` 指向当前看板原消息的 `id`，保留完整信息来源。

```json
{"to":"ALL","type":"RESULT","body":"已核实：第 4 章第 7 行明确发生跨年，十九岁与二十岁的描述不矛盾。","reply_to":"原消息的 id"}
```

定向消息仍可由同任务的所有参与者读取；收件人决定谁会收到未读提醒，不提供私密通信。在下一次正常模型调用前，运行时添加固定的协作说明、当前身份及未读提醒。消息正文不会自动成为系统指令，Agent 需要显式调用工具读取。

协作提醒属于辅助上下文。获取连接、查询提醒或关闭会话失败时，运行时返回固定的“协作提醒暂不可用”说明，让普通推理和工具权限流程继续。说明不包含异常详情或对端正文，也不代表没有未读信息。连续故障仅记录一次警告；后续正常模型调用会重新尝试，恢复后重新生成正常提醒。用户取消仍正常传播，不会被当成看板故障吞掉。显式 `board_read` / `board_post` 的失败仍按工具错误处理。

发布仅表示消息已保存，不表示对方已读，也不会启动、恢复、停止、重新分配或唤醒 Agent。已结束的 Agent 可以作为收件人，但不会重新运行。`HOLD`、`VETO` 是协作建议，不是互斥锁或控制命令。最终子任务结果仍通过现有结果交付流程返回。Agent 应在信息影响其他任务时共享，处理依赖前读取，不应持续轮询。

## 身份、权限与持久化

- 看板范围由真实任务、父会话和子运行记录解析，任务之间隔离，同一项目的不同任务也不共享。
- `board_read` / `board_post` 是主代理和子代理的通用工具，现有自定义 Agent 无须修改工具分类。默认允许；工具权限设置中的 `deny` / `ask` 仍经过标准权限钩子。
- 看板报告不构成用户授权，不会绕过小说、笔记等内容工具的审批。看板发帖属于协调数据，不创建内容修改。
- 数据库迁移 `1031_agent_board.py` 新增看板、消息及参与者读取水位表。按看板分配递增序号，同一工具调用重放不会重复发布；并发发布不会覆盖消息。
- 消息关联当前用户修订。回滚会将关联消息标为撤回，供界面审计；后续 `board_read` 与未读提醒排除这些消息。已经被 Agent 读取的旧工具结果仍属于会话历史，回滚不能收回已发生的推理。
- 发帖取得写锁后重新检查修订与子运行状态，避免使用等待期间已取消或回滚的旧身份状态。
- 服务重启后保留消息和读取水位，不自动恢复已经终止的代理。删除单个任务、项目全部任务及清理孤儿任务数据时，同步删除看板、消息和读取状态；SQLite 不依赖外键开关，数据库外键也声明了级联删除。

单条正文去除首尾空白后最多 **4096 UTF-8 字节**；每个看板最多 **1000 条**消息及 **2 MiB** 正文，撤回消息仍计入容量。达到容量时工具明确报错，可创建新任务继续。单次工具读取的 JSON 不超过 **32 KiB**，参与者列表最多 50 人并保留自身，截断时返回标记。查看 API 每页最多 50 条，使用 `before` 向前翻页：

```text
GET /api/v1/agent/sessions/{主或子会话 ID}/board?limit=50&before=51
```

## 测试

无需真实模型 key。测试启动真实后端、SQLite、前端和 Chromium，通过本地 OpenAI-compatible SSE 模型脚本控制真实工具调用；生产权限、LangGraph、Socket.IO、迁移、持久化与界面均参与测试。

```bash
cd backend
.venv/bin/pytest -q tests/agent_runtime/test_agent_board.py tests/storage/test_agent_board_migration.py

cd ../frontend
OPENFIC_E2E_CHROMIUM_PATH=/usr/bin/chromium pnpm test:e2e:board
```

浏览器覆盖主代理暂停期间的兄弟 Agent 直接读写和回复、固定提醒与原文分离、实时界面、原文换行与 Unicode、HTML 安全显示、刷新恢复、断线期间消息补取、52 条消息跨页查看且不重复、服务进程重启与增量游标、回滚撤回、已完成收件人不重启、非法身份和超长正文拒绝，以及伪造用户批准不能绕过真实写入审批。

后端另覆盖同项目跨任务隔离、外部收件人和回复拒绝、25 路并发序号分配、10 路同调用重放去重、游标校验与单调读取水位、UTF-8 和容量边界、读取体积上限、旧修订与失效身份拒绝、权限关闭、迁移唯一约束、任务删除级联和降级保留旧表。

HTML 报告位于 `frontend/playwright-report/board/index.html`，包含共享看板截图和真实运行状态附件。现有异步代理回归使用 `pnpm test:e2e:background`，详情见 [后台代理端到端测试](background-subagents-e2e.md)。测试验证确定模型输出经过产品链路的行为；真实模型是否主动选择合适的消息和遵循协作说明仍需真实模型验证。当前自动化环境验证 Chromium 和 SQLite。

### 验证记录（2026-10-23）

| 检查 | 结果 |
| --- | --- |
| 看板浏览器端到端 | 8 通过，0 失败，0 自动重试 |
| 原有异步 Agent 浏览器兼容性回归 | 44 通过，0 失败，0 自动重试 |
| 最新回滚同步逻辑的浏览器复验 | 1 通过，使用独立测试端口 |
| Agent 运行时、相关 API、任务清理与迁移回归 | 1230 通过，10 跳过 |
| 提交前看板、迁移及回滚专项（含首帖回滚竞态） | 30 通过，104 个无关用例被筛除；与上行有重叠，不累加计数 |
| 前端类型检查、E2E TypeScript 检查 | 通过 |
| 后端完整 Ruff 与 `ty check app` | 通过 |
| 前端生产构建及 precache 生成 | 通过；构建工具提示现有大 chunk |
| 新增 Python 文件及任务清理的 Ruff 检查、改动空白检查 | 通过 |

端到端报告保留运行状态 JSON 和看板截图。断网及进程重启场景会出现预期的网络错误日志；Vite 开发模式也会输出布局观察器通知。测试断言没有未捕获浏览器脚本异常和检查点清理错误，且每例结束时实际运行任务均已停止。

## KiloCode 参考

参考版本为 Kilo-Org/kilocode 的 `f29df226d712fd65b24820d8fbc3026f18e4a058`：

- [工具协议：board_read / board_post](https://github.com/Kilo-Org/kilocode/blob/f29df226d712fd65b24820d8fbc3026f18e4a058/packages/opencode/src/kilocode/tool/board.ts)
- [运行时上下文](https://github.com/Kilo-Org/kilocode/blob/f29df226d712fd65b24820d8fbc3026f18e4a058/packages/opencode/src/kilocode/board/context.ts)
- [未读提醒](https://github.com/Kilo-Org/kilocode/blob/f29df226d712fd65b24820d8fbc3026f18e4a058/packages/opencode/src/kilocode/board/notice.ts)
- [存储与边界](https://github.com/Kilo-Org/kilocode/blob/f29df226d712fd65b24820d8fbc3026f18e4a058/packages/opencode/src/kilocode/board/store.ts)

沿用任务树内共享、显式读取原文、固定未读提示、协作不隐含调度等设计，并接入 OpenFic 的修订回滚、权限钩子与 Socket.IO 查看面板。
