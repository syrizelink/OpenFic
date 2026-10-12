# OpenFic 插件与可扩展性系统调研

## 调研范围与结论

调研日期：2026-10-11。基于 `main` 的 `4de9dd4c472e4cd7238c74156fff7dd36face22c`（0.12.1）。通过 GitHub compare 接口确认该提交与远端 main 一致。参考文档按本次调研时可访问的版本核对；本文是静态代码调研和工程估算，未实现原型或进行性能、安全验证。

**四类目标均可实现，不需要重写整个项目，但需要建设一层正式的插件宿主。** 最容易起步的是固定位置的 UI 入口、插件工具和项目数据读取；成本最高的是完整 Graph 替换、写入一致性和不可信代码隔离。建议以版本化 SDK、明确 UI 插槽、运行时中间件、Graph Provider 和统一数据命令为核心。

范围应分成两层：

- **业务可编程**：插件能控制已定义的工作流阶段、实现任意拓扑的 Graph、执行自定义工具、访问项目实体、展示自己的 UI。
- **宿主约束**：插件仍遵守数据写入、执行状态、持久化、取消和权限协议。任意 Graph 不等于任意内部状态都能随意改写。

可信本地插件可以先采用进程内执行；面向广泛第三方插件时，需要另外实现隔离运行。不能把第一种方案描述为具有安全沙箱。

## 参考系统的借鉴与边界

| 系统 | 值得借鉴 | 对 OpenFic 的适用边界 |
| --- | --- | --- |
| [Open WebUI Extensibility](https://docs.openwebui.com/features/extensibility/) | Tool、Filter、Action、Pipe 分工；内部代码与外部服务分层 | 适合作为“加工具、改请求、加操作、换执行入口”的分类参考；不直接解决小说实体一致性或编辑器扩展 |
| [Claude Mods](https://code.claude.com/docs/en/plugins/mods/overview) | 事件处理可观察、改写或接管；显式 UI 扩展位置；插件 API | 最接近所需的 UI 与行为扩展；其可信代码权限模型不能直接当作 OpenFic 的隔离方案 |
| [Claude Mods Reference](https://code.claude.com/docs/en/plugins/mods/reference) | `next` 中间件、取消信号、时间预算、错误处理和类型声明 | 可参考接口语义，不必复制所有事件或允许插件替换权限提示 |
| [SillyTavern UI Extensions](https://docs.sillytavern.app/for-contributors/writing-extensions/) | manifest、生命周期、独立 UI 包、事件和 generation interceptor | 开发门槛低；直接暴露可变应用状态会增加升级与冲突成本，OpenFic 更适合提供受控服务接口 |

这些系统可以提供机制参考，但不能作为“支持插件后就自然支持任意 Agent Graph”的证明。Graph 替换必须单独设计。

## 当前代码能复用什么

下列路径均相对于仓库根目录。行号对应调研提交。

| 目标 | 现有基础与代码证据 | 主要缺口 | 相对难度 |
| --- | --- | --- | --- |
| 指定位置添加入口和 UI | `frontend/src/features/app-shell/components/app-layout.tsx`、`app-sidebar.tsx:43`、`status-bar.tsx:209`；设置、工具栏、上下文菜单均有明确组件 | 没有插件 UI 插槽注册表、动态页面宿主及统一卸载协议 | 中 |
| 插件工具 | `backend/app/agent_runtime/tools/registry.py:13` 支持注册与实例化；`tools/base.py:66` 有 HookContext/HookResult | 注册依赖内置模块 import；缺少发现、归属、重名拒绝、注销及动态工具分类 | 低至中 |
| 控制 Workflow 环节 | `tools/base.py:188` 有 pre/post hooks；`context/build_context.py` 分阶段组装上下文；`graph/react_agent.py:665` 集中构建 ReAct 图 | Hook 列表在主/子 Agent 中静态组装；没有覆盖模型、上下文、压缩、节点、会话阶段的公共注册机制 | 中至高 |
| 替换 Agent Graph | `graph/orchestrator/graph.py:212` 独立 Graph 工厂；LangGraph 已负责检查点 | `runner/session_runner.py:163` 固定调用内置工厂；Runner、状态、事件、恢复与版本管理需要共同抽象 | 高 |
| 章节、世界书、角色、笔记交互 | `storage/services/`、`api/routers/`、`agent_runtime/tools/impls/` 已提供 CRUD/工具；`agent_runtime/revisions.py` 有回滚 | SDK、项目范围校验、统一变更通知、写入审计及冲突协议未形成统一边界 | 中；同步更高 |
| 编辑器控制 | 章节用 Tiptap/ProseMirror；`features/writing/lib/editor-config.ts` 集中构造扩展；`components/markdown-editor.tsx:186` 为另一编辑器入口 | 没有公共 Editor Handle；不同编辑器的内容格式、草稿和保存路径不同 | 中；原生扩展较高 |
| 备份 | `desktop/src/main/data-manager.ts:104` 已支持数据目录打包；`desktop/src/main/ipc.ts:565` 附近通过 withBackendRestart 执行备份 | 仅能作为桌面备份基础；缺少通用在线一致性快照和同步协议 | 备份中；双向同步高 |

### 工具 Hook 是基础，尚不是完整中间件

`HookResult` 主要表达继续、interrupt 和输出替换。现有 pre-hook 并不等价于“修改参数、替代执行结果、阻止执行并正常返回”的通用拦截器。

工具调用还分为 prepare/execute 两阶段；`react_agent.py:1269` 的 execute 阶段设置 `openfic_skip_pre_hooks`。直接加一个通用 Hook 列表，容易产生执行两次、恢复后副作用重复或参数在批准后变化的问题。

`ToolRegistry.register()` 当前按名称直接赋值；新增工具还受 `agents/tool_categories.py` 的静态分类约束。插件注册进表并不意味着 Agent 自动能使用它。

### 当前 Graph 比表面上更容易替换，也更容易被低估

父 Graph 当前只有 `START → primary → END`；子 Agent 调度通过持久化 child run 和工具完成，不是固定的多节点父图。这有利于把内置父图包装成默认 Provider。

但是 `SessionRunner` 不只调用 Graph：它使用 `astream_events`、`aget_state`、`aupdate_state`、检查点、interrupt/resume、revision 和消息注入。`runner/event_translator.py:30` 主要认识 LangChain 模型/工具事件；`graph/node_events.py` 另外发送节点事件。

因此，“工厂支持传入插件 Graph”只能证明图可以跑，不能证明消息、恢复、回滚和 UI 全部正确。现有节点跟踪还使用单个 `current_node`，任意并行 Graph 需要节点实例 ID 和活动节点集合，不能仅沿用单节点状态。

### 数据 CRUD 已经齐全，副作用没有完全统一

例如 `storage/services/chapter_service.py` 负责统计和部分索引维护；`tools/impls/chapter/write_chapter.py` 还负责 revision 快照、写入和提交通知。`tools/hooks/chapter_refresh.py:35` 根据内置工具分类与返回 metadata 向 Agent 会话房间发送刷新。

新插件直接调 service 或 REST 可以实现写入，但未必得到 Agent 修改面板、回滚或所有客户端的刷新。仅补一个“插件工具名”无法覆盖 UI、同步任务和外部服务的所有写入来源。

章节编辑器还将 working copy 存入本地数据库，见 `features/writing/hooks/use-writing-working-copy.ts`。`chapter-editor.tsx:319` 的保存路径提交 title/content/wordCount；`api/schemas/chapter.py:23` 的更新模型没有公开的 expected revision 字段。当前本地草稿处理不能直接当作插件并发写入或云同步的完整冲突控制。

## 推荐架构

### 插件包与宿主

建议新增 `backend/app/plugins/` 与 `frontend/src/features/plugins/`，通过公共 SDK 包建立边界。名称均为提案。

插件 manifest 至少包含：`id`、`version`、`apiVersion`、兼容范围、前后端入口、能力声明、依赖、设置 schema。扩展类型分别注册 UI、命令、工具、Hooks、Graph Provider、编辑器行为和后台任务。

后端采用 Python SDK 是复用现有 LangGraph、工具和服务成本最低的路线；前端使用编译后的 JS UI 包。完整插件可以包含两个入口，纯前端或纯后端插件不必同时编写两种语言。外部进程可以以后通过 RPC 适配其他语言。不要为统一插件语言先重写 Python Agent Runtime。

宿主负责安装校验、发现、启停、依赖检查、归属、设置和命名空间存储、日志、注册清理、版本兼容。UI 资源由后端在 SPA catch-all 之前提供专用路径，不能要求修改源码并重新构建主应用才能安装插件。

第一版支持本地目录或包安装、重启生效即可。市场、自动更新、复杂依赖求解与热替换应后置；已有运行中的 Graph 必须固定插件版本，停用和升级不能让待恢复的检查点失去实现。

后端包依赖还需要明确策略：首版宜限制为宿主提供的依赖或插件打包的兼容依赖，避免安装时直接修改宿主 Python 环境。需要冲突版本或重依赖的插件以后使用独立运行环境。设置和普通插件存储不应保存云服务密钥；通过宿主管理的凭据引用与网络服务调用能力访问。跨前后端 RPC 必须携带由宿主建立的插件身份与调用范围，不能信任插件自行提交的身份字段。

### UI：固定插槽加独立 View

建议第一批插槽：

- 主侧栏导航、项目操作菜单。
- 编辑器工具栏、选区菜单。
- Assistant 消息操作、工具结果附加展示。
- 状态栏、设置页。
- 由入口打开的插件页面、侧面板或 Dialog。

按钮、菜单项、状态项先用声明式贡献；复杂 UI 使用插件自己的 View。宿主给 View 提供主题 token、语言、当前项目/实体上下文和 SDK 通信。

可信模式可以挂载 React 组件，需处理 React 单实例与宿主版本兼容；框架独立的复杂页面可以使用 iframe。隔离模式应使用具有明确 sandbox/origin/CSP 的 iframe 和受控消息桥，校验窗口来源及会话身份。iframe 使用与主应用相同的权限或任意宿主 fetch，会削弱隔离。

不建议第一版公开任意 DOM 选择器、React 内部状态或替换任意组件。指定位置加入口能覆盖当前目标，也能稳定维护。移动端需要为侧面板提供页面/抽屉呈现，不应只在桌面布局加插槽。

### Workflow：观察事件与行为中间件分开

事件用于观察与刷新；中间件用于修改、阻止和接管。建议覆盖：

| 阶段 | 可编程行为 |
| --- | --- |
| 会话/用户输入 | 修改提交内容和附件、拒绝或转交指定 Graph |
| 上下文组装 | 增删具名 prompt section、选择上下文来源、改变检索结果 |
| 模型请求与流 | 改变路由或参数、处理输出与流；保留完整消息和 tool call 结构 |
| 工具描述与调用 | 注入工具、改参数、提供替代结果、阻止调用 |
| 节点/子 Agent | 前后置处理、调度或实现替代节点 |
| 压缩与终止 | 自定义策略、观察终止和错误、处理恢复 |
| 数据命令 | 请求写入、观察提交后的变更；外部同步放到异步任务 |

中间件可以借鉴 `(context, input, next)`；限制 next 调用次数，规定稳定的优先级/顺序、返回类型、错误策略、取消和递归规则。不要让多个插件通过共享可变 state 任意竞争。

必须约定执行边界：参数经过插件改写后再做最终宿主校验与审批；prepare 和恢复阶段不能产生不受控的外部副作用。观察型 Hook 超时可跳过；决定写入或权限的 Hook 失败需要显式错误策略，不能默默放行。

“控制任意环节”应理解为每个公开业务阶段都可观察或替换；权限检查和持久化一致性仍由宿主最终执行。可信代码进程内运行时，这只是接口约定，不能防止恶意代码绕过宿主。

### Graph：先支持 LangGraph Provider，再扩展外部 Runtime

第一版可定义 `GraphProvider`：提供稳定 ID、状态 schema 版本、构建 Graph 的工厂、输入/输出适配和所需能力。宿主提供 checkpointer、模型/工具调用、数据命令与事件 sink；任务保存所选 provider、插件版本和状态 schema 版本。

内置 Graph 同样注册为默认 Provider；SessionRunner 通过 Provider 解析而非固定调用 `build_orchestrator_graph()`。自定义 Graph 可以完全替换内置拓扑，同时复用内置节点或构造自己的节点。

应形成以下协议，而不是把 CompiledStateGraph 类型直接当作永久 SDK：

1. 标准输入、任务身份及宿主元数据；插件业务状态使用独立命名空间。
2. 消息、节点实例、工具、usage、interrupt、完成/失败事件。
3. cancel、resume、checkpoint、状态读取和业务回滚的语义。
4. 外部副作用的幂等键，以及重放后哪些结果可以复用。
5. schema 迁移、旧插件版本保留和无法恢复时的明确处理。

近期可以用 LangGraph adapter 实现这些协议。以后接入 JS 或独立服务 Graph 时再增加 RuntimeAdapter，无须让第一版同时承担多语言执行器的成本。

自定义 Graph 的 Agent 节点如果不走宿主模型与工具服务，其 token 统计、工具审批和业务变更记录无法自动保证；要作为 provider 合约明确要求，而非认为 astream_events 会补齐一切。

### 数据：统一命令与提交后事件

建议对外公开 `projects/chapters/worldEntries/characters/notes` 的查询 DTO 与写入命令，内部复用现有 services。不要把 SQLAlchemy session 或 repo 当作正式插件 API。

写入命令应统一处理：

- project/entity 范围校验、输入约束和 expected version 冲突检测。
- Agent 写入的 revision 快照及变更记录；普通插件操作的来源和操作 ID。
- 数据统计、索引失效/更新、提交以及提交后的领域事件。
- UI 查询缓存失效与工作副本冲突处理。

事件应携带实体 ID、版本、来源插件、operation ID 和项目范围，不依赖内置工具名称。Agent 会话、UI 操作、同步任务都经过同一写入边界。

需要可靠增量同步时，使用持久化变更日志或 transactional outbox；Socket.IO 通知本身不能保证离线补偿或消息不丢。日志要包含删除 tombstone，允许游标续传和幂等应用。

### 编辑器：受控命令与原生扩展分层

普通插件通过 Editor Handle 获取活动文档、选区、文本、文档版本，执行带版本检查的替换、选择、滚动和保存操作。所有修改进入 Tiptap transaction、撤销历史、草稿和现有保存路径；插件不能直接改 DOM 或替换数据库内容来冒充编辑器操作。

章节是纯文本编辑器，笔记等使用 Markdown 编辑器，需按 handle 声明能力与格式，不能承诺任意 JSONContent 在所有编辑器中等价。

关键词高亮、快捷键、输入规则、装饰器等可逐步提供声明式接口。任意 Tiptap/ProseMirror 扩展必须在编辑器进程执行，宜作为可信高级能力；Worker/iframe 无法直接注入原生 transaction 插件。扩展改变 schema 时还需要持久化格式和迁移支持，第一版宜限制为不改变 schema 的行为。

动态增删原生扩展可能需要重建 editor；应安排在文档挂载时生效，保存 selection/草稿/撤销语义，或明确下一次打开生效。

## 备份、云同步与插件隔离的成本边界

### 备份与同步需要分别立项

桌面端现有整目录备份由 withBackendRestart 包裹，不能直接视为服务器在线备份 API。建议先提供宿主管理的一致性项目导出/快照，插件只负责加密、上传和调度；恢复操作仍由宿主处理校验与占用。

第一版云备份可以单向上传快照。多设备双向同步还需要冲突策略、删除传播、设备身份、断线续传、资源附件和迁移兼容，成本明显更高。自动合并文本/CRDT 应单独估算。

备份范围必须说明：项目逻辑导出、实例数据目录、附件和索引、插件数据，以及前端尚未保存的 working copy 是不同集合。宿主不能把未保存的浏览器草稿自动算作后端快照的一部分。

### 不可信插件不能只靠权限字段

Python 同进程插件和宿主 React 中的任意 JS 都可突破 SDK 的约定。`capabilities` 在这个模式下是声明与审计，不是可靠的安全边界。

可以分成两个层级：

| 模式 | 适合能力 | 边界与代价 |
| --- | --- | --- |
| 可信插件 | 原生编辑器扩展、原生 LangGraph、自定义复杂 UI | 最快落地；可读取进程可达的资源，需明确可信安装模型 |
| 隔离插件 | UI 页面、纯逻辑 Hooks、代理工具、通过 RPC 调用宿主 | 独立进程/沙箱加受控 RPC；文件、网络、模型和数据能力在宿主侧授权 |

Worker 是线程隔离与终止机制，不等于安全沙箱；子进程也不能自动限制 filesystem/network。桌面 Electron 的 contextIsolation 不能隔离同页面插件代码，当前 `desktop/src/main/windows.ts:147` 附近也有独立 webPreferences 配置要审查。

真正的跨平台不可信代码隔离需要选择受限运行时、操作系统沙箱或容器，并验证 Windows/macOS/Linux 与 Docker 部署。若希望整个 Graph 在隔离进程运行，必须建设 RPC RuntimeAdapter，其成本超过给进程内 Graph 增加工厂注册。

## 改造路径与成本估算

单位为**有效人周**，是工程判断，不是已有原型测量。假定熟悉项目、保留现有功能、采用可信插件模式、完成必要契约测试和两个以上示例；不包括市场、双向同步插件、跨平台强沙箱或图形化 Graph 编排器。阶段成本增量相加，阶段之间存在依赖。

| 阶段 | 具体交付 | 估算 |
| --- | --- | --- |
| P0：验证切面 | 最小 manifest/注册；一个 UI 入口；自定义工具；一份简单双节点 Graph 的启动/审批/取消/恢复验证 | 1–2 人周 |
| P1：可用插件 MVP | 生命周期、设置和日志；少量 UI 插槽/独立 View；工具注册；四类实体的 SDK 查询与基本统一写入；选区编辑命令 | 4–6 人周 |
| P2：Workflow 与完整 Graph Provider | 主/子 Agent Hook 统一、模型/上下文扩展点、Provider 选择与版本保存；标准事件、检查点/恢复合约和兼容测试 | 5–8 人周 |
| P3：第一版稳定 SDK | 更完整 UI 插槽和可信编辑器行为；版本冲突和领域事件补齐；升级停用约束、文档/模板/示例；三种部署方式验证 | 4–7 人周 |
| **合计** | **四类目标的可信插件第一版** | **14–23 人周** |

P0+P1 的 5–8 人周能做出可用 MVP；MVP 对 Graph 的验证不代表完整 Graph SDK 已交付。单人按连续投入约 3.5–6 个月完成上述全部阶段，实际日历时间还需考虑正常维护和需求变更。两名工程师可以并行 UI/SDK 与 Runtime，但数据与恢复协议需先协调，日历时间不会简单减半。

额外项目预算，均需在 P0 后复核：

| 后续能力 | 额外估算 | 假设 |
| --- | --- | --- |
| 单一云存储的单向快照备份示例 | 1–2 人周 | 有宿主一致性导出，含凭据管理、调度、失败重试 |
| 单一服务的多设备双向同步 | 4–8 人周 | 有变更日志与版本冲突；人工处理冲突，不含自动文本合并 |
| 不可信插件隔离 + RPC 执行适配 | 8–16+ 人周 | 宿主 SDK 已稳定；跨平台约束可能扩大范围，需先做技术验证 |
| 可视化 Graph 编排 | 4–8 人周 | 已有可编译节点定义；有画布依赖不代表已具备 Agent Graph 语义 |
| 社区分发/更新基础设施 | 3–6 人周 | 明确包格式和来源策略，含校验、兼容与回退；不含运营审核成本 |

主要持续成本是 SDK 兼容维护。若插件可以 import 内部模块、操作数据库和修改任意 DOM，初期更快，但主应用每次升级都可能变成插件兼容事故。

## 建议用三个插件证明方案

1. **选区润色插件**：在选区菜单加入口，打开插件侧面板，调用宿主模型，将变更作为编辑器 transaction 应用；验证中文输入、撤销、文档切换、Agent 锁定和草稿保存。
2. **自定义审稿 Graph 插件**：替换内置父图，执行“读取 → 审稿 → 用户审批 → 修改”并支持分支/并行；测试取消、断线重放、进程重启恢复、子 Agent、token 统计、revision 回滚及插件升级后的恢复约束。
3. **云备份插件**：创建一致性快照并上传测试存储；测试变更发生时的快照一致性、凭据隔离、失败重试、幂等和浏览器/桌面部署差异。双向同步另做实体版本与删除冲突验证。

现有 `backend/tests/agent_runtime/` 已有 registry、hooks、ReAct、orchestrator、session runner、并发写入与 revision 等测试基础，可复用它们验证内置行为不回退。新增重点是 SDK 契约、多个插件组合、权限与重放语义；无需在调研阶段跑整个应用测试来证明尚未实现的机制。

P0 的验收重点：插件无需改主应用源码即可安装；UI 和后台调用同一宿主能力；自定义 Graph 能实际恢复；插件写入能刷新与回滚；停用后注册被清理，活动任务有明确处理。只通过“按钮出现/Graph 输出文本”的演示不足以估算完整系统成本。

## 建议决策

先实现可信插件宿主，使用 **Python 后端入口 + JS 前端入口 + 版本化 SDK**。把内置工具和 Graph 接入相同注册机制，逐步验证公共 API 足以支撑内置功能。

首批开放固定 UI 插槽、数据命令、插件工具和受控编辑器操作；同时用 P0 验证完整 Graph 恢复协议。之后正式交付 Workflow middleware 和 Graph Provider。单向备份可以较早做示例；双向同步与不可信隔离分别立项。

这条路线能实现所要求的高可扩展性，同时把最昂贵、最容易被低估的部分——数据一致性、Graph 生命周期和安全隔离——明确纳入预算。
