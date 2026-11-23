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

UI 插槽：`sidebar.extensions`、`app.overlay`、`editor.toolbar`、`statusbar`、`settings`。视图可以返回声明式组件树，或引用已构建的 HTML（可使用任意前端框架）。编辑器插槽只允许工具栏按钮，点击后直接执行操作，或通过浮层、对话框显示内容，不允许常驻面板挤占正文区域。

`OpenFic.editor` 访问当前打开的编辑器，支持读取内容/选择区、插入、替换、选区设置、保存和撤销重做。章节编辑器使用原有 Tiptap 和工作副本保存链；Agent 锁定期间拒绝修改。笔记编辑器支持读取选区及订阅选区变化，并支持正文读取、设置、追加和保存；选区写入和撤销等不支持的操作明确报错。

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

声明 `credentials.read` 后，Python 插件可通过 `await context.providers.get_credential(provider_id)` 读取指定提供商的 API Key。未配置或无法解密时返回 `None`；提供商不存在或属于 OAuth 时抛出 `ValueError`。调用前可声明 `providers.read` 并通过业务网关列出提供商；两个权限互不包含。此方法不开放给 iframe SDK，普通提供商列表也不返回密钥。插件后端应避免将密钥写入日志或返回给界面；诊断记录对该接口的参数和结果脱敏。这是 SDK 权限约束，不是对可信 Python 插件的沙箱。

`context.files` 是插件数据目录中的文本文件接口，不等于整个主机文件系统。`context.http.request(method, url, headers=..., json=..., form=..., body=...)` 要求 `network`，目的 hostname 还必须在 `network_hosts` 中。不会自动跟随重定向；正常目标必须 HTTPS，只允许显式声明的 loopback 开发服务使用 HTTP。

`context.oauth.start(...)` 支持 PKCE、随机一次性 state 和十分钟有效期。标准回调为当前后端地址的 `/plugin-oauth/callback`；必须在 OAuth 提供商后台登记相同 URI。成功后令牌存入当前插件的 `oauth.tokens` 密钥，刷新逻辑由插件按提供商协议实现。

完整备份宿主配置时，应同时备份插件目录中的 `.registry.json`、`.data/`、`.secret-key` 和 `.workflows.json`；丢失 `.secret-key` 后加密令牌不能恢复。插件安装包导出不包含这些运行数据。当前宿主使用单后端进程协调生命周期，不承诺多个 worker 共享同一插件目录的并发更新一致性。

限制：普通命令参数 64 KB，SDK 参数及结果 4 MiB；单个存储值 4 MiB、KV 文件 8 MiB；单文件 4 MiB、文本目录配额 40 MiB；HTTP 响应 8 MiB，25 秒超时。命令最长 120 秒。Python 同步阻塞代码仍不能被异步超时强制终止。

## Agent 工具、中间件、定时任务与 Graph

```python
async def sync(context, arguments):
    # 可访问 context.runtime['project_id'] / ['session_id']。
    return {"ok": True}

def sync_detail(arguments, result):
    return "同步成功" if isinstance(result, dict) and result.get("ok") else None

async def prompt(context, event, next):
    return await next({**event, "sections": [
        *event["sections"], {"id": "my-rule", "text": "保持人物一致性", "scope": "system"}
    ]})

def register(host):
    host.register_tool("sync", "手动同步", {"type": "object", "properties": {}}, sync, category="云同步", display_name="同步章节", icon="CloudUpload", title="同步章节", detail=sync_detail)
    host.register_hook("prompt.compose", prompt, priority=10)
    # host.register_graph('custom', factory)
    # host.register_interval(60, background_handler)
    # host.on_dispose(cleanup)
```

动态工具会进入 Agent 工具列表，并沿用内置审批和设置。`category` 和 `display_name` 必须是非空字符串，分别指定自定义分类及工具的界面显示名称；`name` 是机器使用的 ID。分类名称相同的插件工具在智能体设置中归为一组，与内置分类独立。选择分类时只选择当时已注册的工具，之后新增的工具不会自动勾选。默认写工具需要审批；`access_level='readonly'` 可标为只读。工具 ID 具有插件命名空间，禁止覆盖内置工具；工具 schema 不允许远程 `$ref`。中间件改写已审批参数时会重新校验和授权。

可选的 `icon`、`title` 和 `detail` 控制会话工具消息：`icon` 可使用 Lucide 名称或已声明资源中的 PNG、JPEG、WebP、SVG 图标；`title` 默认使用 `display_name`。`detail` 可以是固定字符串，也可以是同步或异步函数，接收本次工具参数和结果，返回字符串或 `None`；JSON 结果会解析为 Python 对象。函数在工具执行结束后运行，结果最多保留 1024 个字符；异常只记录错误类型，不影响工具结果。运行中可显示固定 detail，动态 detail 在执行结束后显示并随消息保存，不会改变提供给模型的工具结果。插件停用或卸载后，历史标题和详情仍可显示；包内图标不可用时使用默认图标。

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
| `app.overlay` | 应用全局浮层；不占布局，需 `ui` 和 `ui.overlay`，支持声明式视图和 iframe |
| `sidebar.extensions` | 全局侧栏入口，点击进入独立页面 |
| `editor.toolbar` | 章节和笔记编辑器工具栏的图标按钮，默认打开浮层。`views[].placement` 可设为 `left-end`（左侧末尾）、`right-start`（右侧开头、撤销前）或 `right-end`（右侧末尾、保存后，默认） |
| `selection.menu` | 对指定来源的选中文本提供操作，按插件声明选择选中后显示、右键显示或两者 |
| `statusbar` | 状态栏文本和图标，可设为不可点击、浮层或对话框 |
| `settings` | 设置分类列表末尾的插件入口，选择后在设置面板中显示插件页面 |

入口通过 manifest 的 `views` 声明。`renderer: "declarative"` 优先使用项目组件原生渲染组件树，也支持显式 Radix Themes 组件、响应式属性和作用域 CSS，声明 `render` 命令并按需绑定业务 `action`；界面状态可由前端本地维护。`renderer: "iframe"` 或省略时继续加载 HTML，允许同一插件混用。详见 [声明式 UI 协议](./declarative-plugin-ui.md)。

`settings` 视图必须声明非空 `title` 和 `icon`，作为设置分类的标题和图标。`icon` 支持 Lucide 图标名或插件包内的 PNG、JPEG、WebP、SVG 图片路径，图片须通过宿主的安全校验。插件负责页面内容；设置面板右上角的关闭按钮由宿主管理，不能隐藏或由插件控制。支持声明式和 iframe 页面。

`editor.toolbar` 还支持 `renderer: "declarative"` 配合 `presentation: "action"`。这类按钮只绑定 `action` 命令，不声明 `render` 或 `entry`。点击时以视图的 `id` 作为操作 ID，发送 `press` 事件和当前编辑器上下文，不打开浮层或对话框。

`selection.menu` 要求 `ui` 和 `selection.read` 权限，使用声明式 `action` 命令。`selectionTriggers` 支持 `selection`、`contextmenu`；`selectionSources` 支持 `chapter`、`note`、`character`、`world-info`、`agent-message` 和 `agent-input`。提示词链编辑器不接入。仅非空且未跨来源的选区会显示菜单；系统触屏选区菜单的行为受设备限制。

```json
{
  "id": "quote",
  "title": "引用",
  "slot": "selection.menu",
  "renderer": "declarative",
  "presentation": "action",
  "action": "quote.create",
  "selectionTriggers": ["selection", "contextmenu"],
  "selectionSources": ["chapter", "note", "character", "world-info", "agent-message", "agent-input"]
}
```

菜单命令的 `value` 和 `context.selection` 包含 `text`、`source`、视口坐标 `bounds`，以及有可用目标时的 `target`。只有选中菜单项后才会将快照发送给对应插件；`selection.read` effect 在该操作期间返回相同快照，其他上下文返回 `null`。插件可执行其他操作，或返回以下 effect 插入关联引用：

```python
async def quote(context, params):
    return {"effects": [{"method": "assistant.quote", "params": {"prompt": "请分析这段内容"}}]}

def register(host):
    host.register_command("quote.create", quote)
```

`assistant.quote` 使用宿主捕获的选区和插件身份，`prompt` 最大 4000 字符；引用包含的编码数据最大 48000 字符。目标项目和 Agent 标签必须可确定且未改变，否则返回错误。引用内容和提示词在发送时作为用户消息内容处理，不提升为系统指令。插件停用或卸载后草稿中的引用不能发送；历史消息仍可显示和恢复。引用绑定原目标标签与任务，会话改变时应重新选择引用。

插件引用复用会话已有的 `of-mention` 引用节点及文本快照，插件标识、提示词和目标会话随引用保存。

`statusbar` 视图必须声明已注册的 `status` 命令和 `presentation`：`none` 不可点击，`popover` 和 `dialog` 打开对应的插件视图。不可点击的视图不声明 `entry`、`render` 或 `action`；可点击视图按 iframe 或声明式视图的常规方式声明内容。`status` 命令返回 `{"items": [...]}`，每一项只能是 `{"type": "text", "text": "..."}`、`{"type": "icon", "name": "Activity"}` 或 `{"type": "asset", "path": "images/icon.svg"}`，按数组顺序显示，不支持自定义组件或样式。包内图片须在 `resources` 范围内，支持 PNG、JPEG、WebP 和安全 SVG，最大 256 KiB。插件状态变化后调用 `context.invalidate_ui(view_id)` 刷新指定视图，省略视图 ID 则刷新该插件全部视图；连接恢复后也会刷新。

iframe 内嵌视图可用 `height` 指定 80–1600px。视图收到项目、章节、插槽、语言和主题上下文；缺少当前编辑器时编辑器 API 明确报错。页面运行在无同源权限的 iframe，CSP 阻止直接联网；允许内联样式以支持框架组件。网络访问走后端 SDK。

`OpenFic.ui` 提供应用内导航、外部 HTTPS 页面、通知、确认、复制、文本下载、当前 UI 上下文和缓存刷新；`OpenFic.assistant.fill` 将文字追加到 Agent 输入框。程序化打开外部页面/剪贴板仍受浏览器平台权限约束。

内嵌 iframe 视图可调用 `OpenFic.ui.resize(height)` 调整自身高度，返回实际采用的高度；要求 `ui` 能力，不能改变其他视图或整个应用。允许 0 高度折叠，通用视图最高 1600px。宿主在窗口尺寸变化时重新应用上限。

常驻 `app.overlay` iframe 的初始尺寸为零，调用 `OpenFic.ui.setOverlayBounds({ x, y, width, height })` 设置相对于视口左上角的像素矩形。尺寸须为非负有限数值，坐标须为有限数值；宿主将矩形限制在视口内并返回实际矩形，视口变化时重新限制。`OpenFic.ready` 返回的上下文包含宿主 `viewport: { width, height }`；视口变化时可通过 `OpenFic.on("ui.viewportChanged", callback)` 获取新尺寸。矩形外的指针事件穿透，矩形内即使内容透明也会拦截事件。插件负责定位、拖动及位置持久化。

全局浮层插件可额外声明 `slot: "app.overlay"` 且 `presentation: "dialog"` 或 `"popover"` 的独立视图，支持 iframe 和声明式渲染；这些视图不会常驻挂载。常驻视图通过 `OpenFic.ui.openOverlay(viewId, anchor?)` 打开同一插件的目标视图，通过 `OpenFic.ui.closeOverlay()` 关闭；声明式视图可在 action effects 中使用对应的 `ui.openOverlay` / `ui.closeOverlay`。浮层必须提供 `anchor: { x, y, width, height }`，以宿主视口左上角为原点，单位为像素；对话框无需锚点。宿主将锚点限制在视口内并处理浮层定位、关闭和焦点。弹层内容可使用 `OpenFic.ui.close()` 或 `ui.close` effect 关闭自身，iframe 可用 `OpenFic.ui.resize()` 调整高度。每个常驻视图同时最多打开一个弹层，打开另一个会替换原弹层；关闭、停用插件或卸载常驻视图时弹层随之移除。

`OpenFic.on` 可订阅 `editor.open/change/selection/close`、`data.changed` 和插件事件。没有 `editor.read` 的视图不会收到编辑器正文；服务端的 `editor.change` hook 也要求读取能力，改写还要求 `editor.write`。异步编辑器结果只在原内容和当前实体仍匹配时应用，避免覆盖用户后续输入。

## 示例与验证

整轮改造对原有功能的回归、发现的问题和修复见 [原有功能回归验证](./plugin-regression-verification.md)。所有智能体默认不启用插件工具；可在智能体设置中按插件声明的分类选择，也可通过 Agent 定义的 `metadata.plugin_tools` 指定完整工具 ID，空列表表示关闭。工具审批设置按显示名称逐个配置允许、询问和拒绝；未配置时只读工具默认允许，写入工具默认询问。

三个插件位于 `examples/plugins/`，安装包位于 `examples/plugins/dist/`。使用说明见 [示例插件](./plugin-examples.md)，测试范围及复现见 [原生插件验证记录](./plugin-native-verification.md)。插件集成测试位于 `backend/tests/plugins/`。

Google Drive 与模型在自动化测试中使用协议仿真，业务后端、数据库、宿主、RPC、iframe 和 Agent 执行链都是真实实现。测试不会访问真实 Google 账户，也没有运行原生桌面安装程序。

### Agent 版本化写入

业务 `api.request` 与资源 CRUD 具有普通用户编辑的语义，不自动把修改归入当前 Agent revision。需要 Agent 回滚、变更记录和审批的操作，应使用后端 `context.agent.tools()` 查询内置工具 schema，再在活跃、版本化会话中调用 `await context.agent.call_tool(name, arguments)`。它保留内置工具的审批、revision、活动记录和刷新通知；嵌套结果归属外层插件工具，不重复生成模型工具结果。不能递归调用其他插件工具。

Drive 的 Agent 工具明确限定为上传备份，因此不会借普通用户 API 覆盖当前会话内的章节；双向写入在独立插件页面由用户执行。

前端也有 `OpenFic.agent.tools/start/send/cancel` 便捷方法。插件 Agent 工具与 RPC/生命周期使用宿主调度锁协调，避免共享数据库 session 并发写入；已开始的自定义 Graph/模型请求不会因移除 UI 入口而被强制杀死，取消运行应使用 Agent 会话控制。
