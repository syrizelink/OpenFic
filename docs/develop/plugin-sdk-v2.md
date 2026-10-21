# 插件 SDK 2.0

本次 SDK 在保持 `api_version: 1` 包兼容的基础上扩展能力。`GET /api/v1/plugins/catalogue` 返回版本、能力、UI 插槽、事件、可操作业务路由与完整 OpenAPI schema。新增插件应以该目录为接口依据，避免直接导入应用内部模块。

## 能力矩阵

| 范围 | API |
| --- | --- |
| 项目、卷、章节、笔记及分类、角色及关系、世界书 | `context.api.request` / `OpenFic.api.request`，复用业务 CRUD、移动、排序、批量、检索等接口 |
| 提示词链、规则、技能及引用、Agent 定义、记忆 | 对应业务 API 与 schema |
| 会话、任务、修订、摘要、索引、后台作业、导入导出 | 对应业务 API；会话启动、发送、取消、恢复等沿用内置执行器 |
| 模型、提供商、应用设置、仪表盘、审计、隧道 | 对应业务 API，分别要求明确的读/写能力 |
| 插件数据 | 独立 JSON KV、加密密钥存储、插件目录内文本文件、`assets.read` 包内只读资源 |
| 网络与模型 | 显式网络域名、受限 HTTP 客户端；已配置模型的调用接口 |
| Agent 扩展 | 注册动态工具、事件中间件、编译后的 LangGraph/Runnable 提供者 |
| UI | 多位置声明式原生组件或 iframe 视图、导航、通知、下载、剪贴板、编辑器操作和事件 |

这些能力是可信插件 SDK 的接口约束。原生 Python 插件仍在后端进程内运行，不是隔离沙箱。SDK 不开放认证管理、宿主插件管理或任意内部 URL。

## Python

```python
from app.plugins import PluginContext

async def save_note(context: PluginContext, params):
    note = await context.notes.create(
        {"title": "插件笔记", "content": params["text"]}, params["projectId"]
    )
    await context.storage.set("lastNote", note["id"])
    return note

def register(host):
    host.register_command("notes.save", save_note)
```

`context.resource(name)` 提供常用 list/get/create/update/delete；复杂路由使用 `context.api.request(method, path, json=..., query=..., form=..., files=...)`。业务路径不含 `/api/v1` 前缀。JSON、表单、base64 上传和二进制下载均有独立表示。接口校验、锁定检查、计数、保存副作用和后台作业沿用原业务逻辑。

资源读写分别声明 `<resource>.read` / `<resource>.write`；只读项目统计的旧接口保持兼容。写权限不隐含读权限。共享密码部署仍不是多租户项目授权系统。

## UI 与编辑器

UI 插槽：`sidebar.extensions`、`project.toolbar`、`editor.toolbar`、`editor.context`、`editor.panel`、`assistant.toolbar`、`assistant.above-prompt`、`statusbar`、`settings.plugins`、`dashboard`。视图可以返回声明式组件树，或引用已构建的 HTML（可使用任意前端框架）。编辑器插槽只允许工具栏按钮，点击后通过浮层或对话框显示内容，不允许常驻面板挤占正文区域。

`OpenFic.editor` 访问当前打开的编辑器，支持读取内容/选择区、插入、替换、选区设置、保存和撤销重做。章节编辑器使用原有 Tiptap 和工作副本保存链；Agent 锁定期间拒绝修改。笔记编辑器支持正文读取、设置、追加和保存；不支持的选择区/撤销操作明确报错。

## 插件包格式

安装包为包含根目录 `plugin.json` 的原生 OpenFic ZIP。前端框架代码由插件开发者预先构建为 HTML/JS 资源，或通过声明式协议返回宿主组件树。

Claude Mods 原包兼容支持已移除，包括包转换、JS/TS/JSX 执行和 CLI 事件映射。原包与旧转换包均不再安装或加载。已有 Mod 的磁盘目录和数据不会自动删除；原生插件及其数据继续使用。

## SDK 分发与调用约定

- Python 公共入口：`from app.plugins import PluginContext`。`context` 的数据对象都是 JSON DTO；常用资源还有 `chapters`、`projects`、`notes`。
- 前端：宿主在 iframe 应用脚本之前自动初始化全局 `OpenFic`。React/Vue/Svelte 可以直接使用，不要求插件共享主应用的框架实例。
- 独立包：`packages/plugin-sdk` 是 `@openfic/plugin-sdk@2.0.0` 的无依赖模块包装及 TypeScript 声明，可用本地 `file:` 依赖或 `npm pack` 安装；本任务没有发布 npm。声明同时由 `/api/v1/plugins/sdk.d.ts` 提供。
- 所有业务操作的准确路径、HTTP 方法、请求字段与响应类型，以 `/api/v1/plugins/catalogue` 的 `operations` 和 OpenAPI 为准。`context.resource(name)` 的便捷方法覆盖常见 CRUD；不是每个业务对象都存在全部 CRUD 方法，特殊对象使用目录中的实际路径。

```typescript
import OpenFic from '@openfic/plugin-sdk';
const context = await OpenFic.ready;
const chapter = await OpenFic.chapters.get(context.chapterId!);
await OpenFic.chapters.update(context.chapterId!, { content: '新内容' });
const unsubscribe = OpenFic.on('data.changed', event => console.log(event));
```

业务 API 支持表单及文件上传，二进制响应返回 `{ base64, mime, filename }`。上传的 `files` 项形如 `{ field, name, mime, base64 }`。SDK 不提供原始 ORM 写入捷径，因此校验、项目计数、锁定保护和后台作业由现有业务服务维护。SDK 写操作按业务请求提交；需要多个动作共同回滚时，应使用应用已有的事务操作，不能假定多个独立 HTTP 调用天然原子。

## 存储、密钥、文件、网络与 OAuth

`context.storage` / `OpenFic.storage` 提供 `get/set/delete/keys`；每个插件独立持久化，更新保留，卸载删除。`context.secrets` 的后端 API 相同，使用 Fernet 加密；前端只能写入、删除和列出自己的密钥名称，不能读回值。标记 `secret: true` 的设置也加密保存，管理接口和 iframe 上下文不返回实际值；保存空输入保留已有值。

`context.files` 是插件数据目录中的文本文件接口，不等于整个主机文件系统。`context.http.request(method, url, headers=..., json=..., form=..., body=...)` 要求 `network`，目的 hostname 还必须在 `network_hosts` 中。不会自动跟随重定向；正常目标必须 HTTPS，只允许显式声明的 loopback 开发服务使用 HTTP。

`context.oauth.start(...)` 支持 PKCE、随机一次性 state 和十分钟有效期。标准回调为当前后端地址的 `/plugin-oauth/callback`；必须在 OAuth 提供商后台登记相同 URI。成功后令牌存入当前插件的 `oauth.tokens` 密钥，刷新逻辑由插件按提供商协议实现。

完整备份宿主配置时，应同时备份插件目录中的 `.registry.json`、`.data/`、`.secret-key` 和 `.workflows.json`；丢失 `.secret-key` 后加密令牌不能恢复。插件安装包导出不包含这些运行数据。当前宿主使用单后端进程协调生命周期，不承诺多个 worker 共享同一插件目录的并发更新一致性。

限制：普通命令参数 64 KB，SDK 参数及结果 4 MiB；单个存储值 4 MiB、KV 文件 8 MiB；单文件 4 MiB、文本目录配额 40 MiB；HTTP 响应 8 MiB，25 秒超时。命令最长 120 秒。Python 同步阻塞代码仍不能被异步超时强制终止。

## Agent 工具、中间件、定时任务与 Graph

```python
async def sync(context, arguments):
    # 可访问 context.runtime['project_id'] / ['session_id']。
    return {"ok": True}

async def prompt(context, event, next):
    return await next({**event, "sections": [
        *event["sections"], {"id": "my-rule", "text": "保持人物一致性", "scope": "system"}
    ]})

def register(host):
    host.register_tool("sync", "手动同步", {"type": "object", "properties": {}}, sync)
    host.register_hook("prompt.compose", prompt, priority=10)
    # host.register_graph('custom', factory)
    # host.register_interval(60, background_handler)
    # host.on_dispose(cleanup)
```

动态工具会进入 Agent 工具列表，并沿用内置审批和设置。默认写工具需要审批；`access_level='readonly'` 可标为只读。工具名称具有插件命名空间，禁止覆盖内置工具；工具 schema 不允许远程 `$ref`。中间件改写已审批参数时会重新校验和授权。

中间件按 priority、插件 ID 和注册顺序运行，`next` 最多调用一次；允许观察、改写、拒绝或返回自己的结果。同插件内部可串联多个 handler；由 handler 的 SDK 调用引起的重入会跳过自身，防止死锁。异常进入插件日志。每个 handler 上限 30 秒。已提交的数据变更通知失败不会把成功写入伪装成失败。

实际接入点包括：会话创建与取消、回合开始与完成、模型调用前、用户提交、上下文组装、系统提示词整合与分段、最终提示上下文、工具描述/调用/结果、子 Agent 启动、业务数据变化和编辑器变化。模型调用前可以通过 `turn.step` 返回 `model`（已配置的模型记录 ID）路由模型。部分历史/编辑器交互只提供观察或消息桥，不能通过返回任意对象替换整个主应用。

`register_interval(seconds, handler)` 要求 `timers`，间隔 5 秒至 24 小时，宿主为每次执行创建数据库 session；停用、更新、卸载时取消并等待清理。`on_dispose` 也在激活失败时执行。

Graph factory 签名为 `factory(context, model)`，返回编译后的 StateGraph 或异步 Runnable。它应接收 `messages`，并接受宿主传入的运行配置。`OpenFic.workflow.select(projectId, providerName)` 按项目选择当前插件的 Graph；传 `null` 恢复内置执行器。选择在后续回合生效，停用提供者时回退内置执行器。每个项目只有一个有效选择。

自定义 Graph 使用 `context.agent.context_messages(messages)` 获取经过内置上下文构建及插件处理的消息，使用 `context.models.invoke(model, messages)` 保持模型流式事件与重试。使用 LangChain Tool 的真实调用事件记录工具结果，避免只在 Graph state 中追加 ToolMessage，导致应用对话里缺失工具结果。handoff 示例展示了完整做法。

`context.models.create(model_id)` / `complete(messages, model_id)` 复用已配置模型；要求 `agent.models`。`context.agent.start/send/cancel` 提供常用会话控制，要求 `agent.invoke` 以及相应 `sessions.read/write`；恢复、审批、分叉、回滚、附件等完整操作由业务目录提供。

### 已提交用量与回合完成通知

`register_hook("usage.recorded", handler)` 在内置主 Agent 或子 Agent 的费用已提交数据库后通知；`register_hook("turn.settled", handler)` 在成功回合完成持久化后通知。两者要求 `agent.hooks`。handler 签名沿用中间件，但**返回值不修改费用或执行结果**，`hooks.preview` 不能伪造这些通知。每个观察者获得独立载荷副本和数据库 session，上限 3 秒；异常仅写插件日志，不将已成功的费用提交改成失败。此机制按运行流程尽力送达，不提供持久化消息队列或停用期间的历史回放；同步阻塞 Python 代码仍不受异步超时强制隔离。

`usage.recorded` 包含唯一 `event_id`、`session_id/task_id/project_id/revision_id`、`cost`、`token_input/token_output/token_cache`、`currency: "USD"`、可用时的 `model_id`、`usage_kind` 和 `created_at`。cache 属于 input 子集，不应重复加到总 token。费用采用宿主模型配置的美元价格，不代表模型服务商实际账单；`model_id` 在压缩计费及某些子 Agent 通知中可能为空。子 Agent 同时带 `parent_session_id/is_subagent`，revision 指向父回合；父事件不重复包含子 Agent 的费用。

`turn.settled` 包含 `session_id/task_id/project_id/revision_id/status/created_at`，目前 `status` 仅为 `completed`。失败/取消不发送该成功通知。按 session + revision 聚合，可以避免把中断回合的费用计入下一次成功回合；每日统计仍应保留已经产生的费用。`turn.complete` 是较早的可改写执行钩子，不能用作数据库费用已结算的信号。

## UI 插槽与操作细节

| 插槽 | 位置与呈现 |
| --- | --- |
| `app.overlay` | 应用全局原生浮层；不占布局，需 `ui.overlay`，只支持声明式视图 |
| `sidebar.extensions` | 全局侧栏入口，点击进入独立页面 |
| `project.toolbar` | 项目列表与项目写作侧栏的入口 |
| `editor.toolbar` | 章节和笔记编辑器现有工具栏内的图标按钮，默认打开浮层 |
| `editor.context` | 旧入口别名：在编辑器工具栏显示按钮，默认打开浮层；不改写内置右键菜单 |
| `editor.panel` | 旧入口别名：在编辑器工具栏显示按钮，默认打开对话框；不再显示常驻面板 |
| `assistant.toolbar` | Agent 输入区域的插件入口 |
| `assistant.above-prompt` | Agent 输入框上方的常驻区域 |
| `statusbar` | 状态栏入口，展开浮动插件视图 |
| `settings.plugins` | 设置内插件区域的附加视图 |
| `dashboard` | 仪表盘中的常驻区域 |

入口通过 manifest 的 `views` 声明。`renderer: "declarative"` 优先使用项目组件原生渲染组件树，也支持显式 Radix Themes 组件、响应式属性和作用域 CSS，绑定 `render/action` 后端命令；`renderer: "iframe"` 或省略时继续加载 HTML，允许同一插件混用。详见 [声明式 UI 协议](./declarative-plugin-ui.md)。

iframe 内嵌视图可用 `height` 指定 80–1600px。视图收到项目、章节、插槽、语言和主题上下文；缺少当前编辑器时编辑器 API 明确报错。页面运行在无同源权限的 iframe，CSP 阻止直接联网；允许内联样式以支持框架组件。网络访问走后端 SDK。

`OpenFic.ui` 提供应用内导航、外部 HTTPS 页面、通知、确认、复制、文本下载、当前 UI 上下文和缓存刷新；`OpenFic.assistant.fill` 将文字追加到 Agent 输入框。程序化打开外部页面/剪贴板仍受浏览器平台权限约束。

内嵌 iframe 视图可调用 `OpenFic.ui.resize(height)` 调整自身高度，返回实际采用的高度；要求 `ui` 能力，不能改变其他视图或整个应用。允许 0 高度折叠，通用视图最高 1600px，对话输入框上方最高为 420px 或窗口高度的 45%。宿主在窗口尺寸变化时重新应用上限。

`OpenFic.on` 可订阅 `editor.open/change/selection/close`、`data.changed` 和插件事件。没有 `editor.read` 的视图不会收到编辑器正文；服务端的 `editor.change` hook 也要求读取能力，改写还要求 `editor.write`。异步编辑器结果只在原内容和当前实体仍匹配时应用，避免覆盖用户后续输入。

## 示例与验证

整轮改造对原有功能的回归、发现的问题和修复见 [原有功能回归验证](./plugin-regression-verification.md)。插件工具默认由 Build 显式加入，Plan 和子 Agent 不再无条件获得插件工具；可通过 Agent 定义的 `metadata.plugin_tools` 指定完整插件工具名，空列表表示关闭。

三个插件位于 `examples/plugins/`，安装包位于 `examples/plugins/dist/`。使用说明见 [示例插件](./plugin-examples.md)，测试范围及复现见 [原生插件验证记录](./plugin-native-verification.md)。新增集成测试位于 `backend/tests/plugins/`；浏览器测试 `frontend/e2e/plugin-sdk.spec.ts` 覆盖三个示例、旧 Mod 包拒绝，以及使用独立类型包的 React 插件。旧项目统计仍由 `frontend/e2e/plugins.spec.ts` 回归。

Google Drive 与模型在自动化测试中使用协议仿真，业务后端、数据库、宿主、RPC、iframe 和 Agent 执行链都是真实实现。测试不会访问真实 Google 账户，也没有运行原生桌面安装程序。

### Agent 版本化写入

业务 `api.request` 与资源 CRUD 具有普通用户编辑的语义，不自动把修改归入当前 Agent revision。需要 Agent 回滚、变更记录和审批的操作，应使用后端 `context.agent.tools()` 查询内置工具 schema，再在活跃、版本化会话中调用 `await context.agent.call_tool(name, arguments)`。它保留内置工具的审批、revision、活动记录和刷新通知；嵌套结果归属外层插件工具，不重复生成模型工具结果。不能递归调用其他插件工具。

Drive 的 Agent 工具明确限定为上传备份，因此不会借普通用户 API 覆盖当前会话内的章节；双向写入在独立插件页面由用户执行。

前端也有 `OpenFic.agent.tools/start/send/cancel` 便捷方法。插件 Agent 工具与 RPC/生命周期使用宿主调度锁协调，避免共享数据库 session 并发写入；已开始的自定义 Graph/模型请求不会因移除 UI 入口而被强制杀死，取消运行应使用 Agent 会话控制。
