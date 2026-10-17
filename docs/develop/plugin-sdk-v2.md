# 插件 SDK 2.0

本次 SDK 在保持 `api_version: 1` 包兼容的基础上扩展能力。`GET /api/v1/plugins/catalogue` 返回版本、能力、UI 插槽、事件、可操作业务路由与完整 OpenAPI schema。新增插件应以该目录为接口依据，避免直接导入应用内部模块。

## 能力矩阵

| 范围 | API |
| --- | --- |
| 项目、卷、章节、笔记及分类、角色及关系、世界书 | `context.api.request` / `OpenFic.api.request`，复用业务 CRUD、移动、排序、批量、检索等接口 |
| 提示词链、规则、技能及引用、Agent 定义、记忆 | 对应业务 API 与 schema |
| 会话、任务、修订、摘要、索引、后台作业、导入导出 | 对应业务 API；会话启动、发送、取消、恢复等沿用内置执行器 |
| 模型、提供商、应用设置、仪表盘、审计、隧道 | 对应业务 API，分别要求明确的读/写能力 |
| 插件数据 | 独立 JSON KV、加密密钥存储、插件目录内文本文件 |
| 网络与模型 | 显式网络域名、受限 HTTP 客户端；已配置模型的调用接口 |
| Agent 扩展 | 注册动态工具、事件中间件、编译后的 LangGraph/Runnable 提供者 |
| UI | 多位置 iframe 视图、导航、通知、下载、剪贴板、编辑器操作和事件 |

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

UI 插槽：`sidebar.extensions`、`project.toolbar`、`editor.toolbar`、`editor.context`、`editor.panel`、`assistant.toolbar`、`assistant.above-prompt`、`statusbar`、`settings.plugins`、`dashboard`。视图入口都是已构建的 HTML，可使用任意前端框架。

`OpenFic.editor` 访问当前打开的编辑器，支持读取内容/选择区、插入、替换、选区设置、保存和撤销重做。章节编辑器使用原有 Tiptap 和工作副本保存链；Agent 锁定期间拒绝修改。笔记编辑器支持正文读取、设置、追加和保存；不支持的选择区/撤销操作明确报错。

## Claude Mods

可直接安装含 `.claude-plugin/plugin.json` 与 `hooks/hooks.json` 的 ZIP（也接受单层仓库目录包装）。原包保留，并生成宿主 manifest 和独立管理视图。JS/TS/JSX/TSX 模块在 QuickJS 中执行，转换器随宿主分发，不依赖用户安装 Node。

已实现的映射包含模块加载、`register(on, options)`、匹配器、`next` 中间件、配置默认值、命令和工具注册、提示词事件、基本声明式 UI、控件回调、KV、作用域文件和 HTTP/模型桥。CPU、内存和异步执行有边界。

Claude 的终端、组织策略、原生权限对话框、MCP 子进程、Node 内建模块、外部 Client 渲染器等没有通用等价实现。兼容结果与警告随插件列出；shell hooks 不会自动执行。兼容性不等于完整运行 Claude Code。

参考：[Claude Mods](https://code.claude.com/docs/en/plugins/mods/overview)、[官方类型](https://github.com/anthropics/claude-code/blob/main/mods/types/claude-code.d.ts)、[LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/use-graph-api)。

## SDK 分发与调用约定

- Python 公共入口：`from app.plugins import PluginContext`。`context` 的数据对象都是 JSON DTO；常用资源还有 `chapters`、`projects`、`notes`。
- 前端：加载宿主的 `../../sdk.js` 后使用全局 `OpenFic`。React/Vue/Svelte 可以直接使用，不要求插件共享主应用的框架实例。
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

## UI 插槽与操作细节

| 插槽 | 位置与呈现 |
| --- | --- |
| `sidebar.extensions` | 全局侧栏入口，点击进入独立页面 |
| `project.toolbar` | 项目列表与项目写作侧栏的入口 |
| `editor.toolbar` | 章节工具栏下的插件入口 |
| `editor.context` | 章节编辑器的上下文操作入口区域；当前不改写内置右键菜单项 |
| `editor.panel` | 章节编辑器中的常驻插件面板 |
| `assistant.toolbar` | Agent 输入区域的插件入口 |
| `assistant.above-prompt` | Agent 输入框上方的常驻区域 |
| `statusbar` | 状态栏入口，展开浮动插件视图 |
| `settings.plugins` | 设置内插件区域的附加视图 |
| `dashboard` | 仪表盘中的常驻区域 |

入口通过 manifest 的 `views` 声明，内嵌视图可用 `height` 指定 80–1600px。视图收到项目、章节、插槽、语言和主题上下文；缺少当前编辑器时编辑器 API 明确报错。页面运行在无同源权限的 iframe，CSP 阻止直接联网；允许内联样式以支持框架组件。网络访问走后端 SDK。

`OpenFic.ui` 提供应用内导航、外部 HTTPS 页面、通知、确认、复制、文本下载、当前 UI 上下文和缓存刷新；`OpenFic.assistant.fill` 将文字追加到 Agent 输入框。程序化打开外部页面/剪贴板仍受浏览器平台权限约束。

`OpenFic.on` 可订阅 `editor.open/change/selection/close`、`data.changed` 和插件事件。没有 `editor.read` 的视图不会收到编辑器正文；服务端的 `editor.change` hook 也要求读取能力，改写还要求 `editor.write`。异步编辑器结果只在原内容和当前实体仍匹配时应用，避免覆盖用户后续输入。

## Claude Mods 兼容边界

| 能力 | 本宿主支持程度 |
| --- | --- |
| 原始目录 ZIP、单层包装目录、`hooks.json` modules | 直接导入；保留源文件并生成宿主视图 |
| JS/MJS/CJS/TS/JSX/TSX、相对模块、JSON、type-only imports | Sucrase + QuickJS；不需要系统 Node |
| `register(on, options)`、matcher、`.catch`、`next` | 支持常见观察、改写、短路及真实宿主 continuation |
| command/tool register | 映射到命令 UI 和命名空间 Agent 工具 |
| prompt/tool/turn/session/agent 事件 | 映射到已接入的宿主事件；不实现 Claude 的所有事件 |
| `ui.resolve` 与 Box/Text/Button/Input/Select/Link/Code/Markdown | 基本树渲染和回调；不复制终端布局与键盘系统 |
| `store`、基础 `state`、文件、HTTP、模型 | 常用方法映射到插件作用域服务；不是 Claude 项目工作目录 |
| `clock.now/sleep` | 支持；原生 SDK 的周期任务使用 register_interval |
| `turn.step` async generator | 可执行预调用控制流，不提供替换 Claude token stream 的等价能力 |
| shell hooks、process/MCP、组织权限/优先级、Client、音频 | 不自动执行或不支持；相关事件/API 无等价保证 |

QuickJS 上限 96 MiB，单段同步执行约 1 秒，单次异步 Mod 事件 25 秒。此运行时提供资源约束和受控桥，但没有宣称经过独立安全审计。导入仍需可信来源确认。Mod 的原生配置、终端行为、权限提升、文件系统语义不可能完整复制。

## 示例与验证

三个插件位于 `examples/plugins/`，安装包位于 `examples/plugins/dist/`。使用说明见 [示例插件](./plugin-examples.md)，测试范围及复现见 [验证记录](./plugin-sdk-verification.md)。新增集成测试位于 `backend/tests/plugins/`；浏览器测试 `frontend/e2e/plugin-sdk.spec.ts` 覆盖三个示例、原格式 TSX Mod，以及使用独立类型包的 React 插件。旧项目统计仍由 `frontend/e2e/plugins.spec.ts` 回归。

Google Drive 与模型在自动化测试中使用协议仿真，业务后端、数据库、宿主、RPC、iframe 和 Agent 执行链都是真实实现。测试不会访问真实 Google 账户，也没有运行原生桌面安装程序。

### Agent 版本化写入

业务 `api.request` 与资源 CRUD 具有普通用户编辑的语义，不自动把修改归入当前 Agent revision。需要 Agent 回滚、变更记录和审批的操作，应使用后端 `context.agent.tools()` 查询内置工具 schema，再在活跃、版本化会话中调用 `await context.agent.call_tool(name, arguments)`。它保留内置工具的审批、revision、活动记录和刷新通知；嵌套结果归属外层插件工具，不重复生成模型工具结果。不能递归调用其他插件工具。

Drive 的 Agent 工具明确限定为上传备份，因此不会借普通用户 API 覆盖当前会话内的章节；双向写入在独立插件页面由用户执行。

前端也有 `OpenFic.agent.tools/start/send/cancel` 便捷方法。插件 Agent 工具与 RPC/生命周期使用宿主调度锁协调，避免共享数据库 session 并发写入；已开始的自定义 Graph/模型请求不会因移除 UI 入口而被强制杀死，取消运行应使用 Agent 会话控制。
