# 声明式插件 UI

`views[].renderer` 明确决定渲染方式，不分析插件代码来猜测。同一插件可以混用两种视图：

```json
{
  "views": [
    {"id": "weather", "title": "Weather", "slot": "assistant.above-prompt", "renderer": "declarative", "render": "weather.render", "action": "weather.action"},
    {"id": "dashboard", "title": "Dashboard", "renderer": "iframe", "entry": "frontend/index.html"}
  ]
}
```

省略 `renderer` 默认 `iframe`，旧插件无须修改。iframe 的 `entry` 必须引用 `frontend/` 下的 HTML；声明式视图不能声明 `entry`，必须声明已注册的 `render/action` 命令和 `ui` 能力，不能把 SDK 方法绑定为这两个命令。缺少绑定命令时启用失败，并在管理页面显示原因。

## 渲染与事件

宿主通过认证接口 `POST /plugins/{id}/views/{viewId}/render` 调用绑定的后端命令，传入 `{viewId, slot, columns, context}`。命令返回组件树，例如：

```python
async def render(context, params):
    return {"tree": {"type": "Button", "props": {"label": "同步", "onPress": "sync"}}}

async def action(context, params):
    if params["id"] == "sync":
        # 执行业务操作，更新插件持久化状态。
        await context.storage.set("last_sync", "done")

def register(host):
    host.register_command("weather.render", render)
    host.register_command("weather.action", action)
```

点击后，宿主通过同一路径的 `/action` 调用绑定的事件命令，参数包含 `{id: "sync", event: "press", value: null, context, viewId, slot}`。后端处理状态后，宿主重新获取组件树。主动刷新可通过 `context.host.emit("ui.invalidate", {}, context.plugin_id)` 发出通知，由已有宿主事件轮询接收。

公开 TypeScript 类型 `PluginView/UINode/UIProps/UIDocument/UIRenderRequest/UIEventRequest` 随 `@openfic/plugin-sdk` 提供。可安装的混合视图示例在 `frontend/e2e/fixtures/plugin-declarative`。

## 编辑器与浏览器宿主操作

声明式 action 可以返回 `UIActionResult`，通过已有前端 SDK 桥执行宿主操作，不需要 iframe 或插件 JS：

```python
async def action(context, params):
    if params["id"] == "insert":
        return {"effects": [
            {"method": "editor.insert", "params": {"text": "插入的文字"}, "discardResult": True},
            {"method": "editor.save"}
        ], "next": "saved"}
    if params["id"] == "saved":
        # params["value"] 为按顺序返回的结果数组；discardResult 项为 null。
        await context.storage.set("message", "已插入并保存")
```

支持编辑器 read/insert/replaceSelection/setContent/setSelection/focus/save/undo/redo，以及 `ui.navigate/openExternal/toast/confirm/copy/download/invalidate/context/tools` 和 `assistant.fill`。每项沿用现有 SDK 能力检查和编辑器锁检查，按顺序执行；失败时停止后续操作和回调。`ui.confirm` 返回布尔值，需要插件在 next 回调中判断后再执行后续操作。敏感覆盖操作也可以使用 `AlertDialog` 组件直接确认。

只有用户 action 的响应会执行 effects，render 文档不会执行。每批最多 16 项，连续最多 4 批；未知方法、无效参数对象会在执行整批前被拒绝。离开视图后停止尚未执行的操作与回调。回调仍只能调用该视图绑定的 action，不能指定其他 RPC 命令。

`next` 通过 `event="change"` 回传结果，沿用事件值的大小限制。对无需读取返回值的编辑器写操作设置 `discardResult: True`，避免传回完整章节；`editor.read` 可传 `{"summary": True}`，返回元信息、`contentLength` 和最多 1000 字符的选区文本，不返回正文。

Python 插件可使用 `await context.call("workflow.select", {"projectId": project_id, "provider": "handoff"})` 等公共 SDK 方法，能力检查与前端 SDK 相同。四个 1.1.0 示例需要包含上述宿主操作支持的 OpenFic 版本。

## 组件名称和优先级

不带前缀的名称先查找项目组件，再查找 Radix Themes 组件。`Spinner` 使用项目 Spinner，`Select` 使用项目 `LabeledSelect`，`Tooltip` 使用项目 `InfoTooltip`。需要明确选择时使用 `Project.Spinner`、`Radix.Spinner`、`Radix.Tooltip` 或 `Radix.Select.Root`。复合组件保留 Radix 的名称与父子结构，例如 `Dialog.Root → Dialog.Trigger / Dialog.Content → Dialog.Title`。

目录覆盖 **122 个 Radix Themes 组件及子组件入口、10 个项目组件**。这不是任意 npm 组件加载器，也不开放 Radix 内部 hook、Slot、Portal、ThemePanel 或所有 Radix Primitives 包；Portal 由宿主管理。

| 项目组件 | 用途与权限 |
| --- | --- |
| `Spinner`、`CircularProgress` | 项目加载和进度显示 |
| `UnitTextField`、`StepperNumberInput` | 带单位输入、步进数字输入 |
| `LabeledSelect`（别名 `Select`）、`SearchableSelect` | 带标签或可搜索的选项；复用桌面和移动端实现 |
| `ModelIdSelect`（别名 `ModelSelector`） | 读取已配置模型，`taskType` 为 `llm/embedding/rerank`；需 `models.read` |
| `ProjectSelectField`（别名 `ProjectSelector`）、`ProjectGridSelector` | 读取项目列表；需 `projects.read` |
| `InfoTooltip`（别名 `Tooltip`） | 项目桌面悬停及触屏提示 |

模型选择器的值是已配置模型记录的 `id`，不是远端模型名称；`allowCustomValue` 可允许自定义名称。项目选择器返回项目 ID，空字符串表示无绑定。数据通过插件 SDK 网关读取，服务端校验能力，缺少能力时渲染接口返回错误。数据变更事件会刷新选择器数据。

Radix Families：`AccessibleIcon`、`AlertDialog`、`AspectRatio`、`Avatar`、`Badge`、`Blockquote`、`Box`、`Button`、`Callout`、`Card`、`Checkbox`、`CheckboxCards`、`CheckboxGroup`、`Code`、`Container`、`ContextMenu`、`DataList`、`Dialog`、`DropdownMenu`、`Em`、`Flex`、`Grid`、`Heading`、`HoverCard`、`IconButton`、`Inset`、`Kbd`、`Link`、`Popover`、`Progress`、`Quote`、`Radio`、`RadioCards`、`RadioGroup`、`ScrollArea`、`Section`、`SegmentedControl`、`Select`、`Separator`、`Skeleton`、`Slider`、`Spinner`、`Strong`、`Switch`、`TabNav`、`Table`、`Tabs`、`Text`、`TextArea`、`TextField`、`Theme`、`Tooltip`、`VisuallyHidden`。有 Root/Item/Content 等子组件的 family 需要使用子组件名称。

复杂选择器、步进输入等项目组件的 `className/style` 及 DOM 属性作用于包装容器；`InfoTooltip.className` 沿用项目组件行为，作用于弹层内容。选择器如需分别设置触发器和弹层样式，使用目录中该组件提供的 `triggerClassName/contentClassName`。

准确的名称、每个组件的属性、响应式支持和权限可从 `GET /plugins/catalogue` 或 `sdk.api.catalogue()` 的 `ui` 字段查询：组件属性由 `common`、Radix 专用的 `radixCommon` 及组件自身 `props` 合并，组件自身优先。此目录及 SDK TypeScript 类型由当前安装的 Radix 版本生成，维护时运行：

```sh
node frontend/scripts/generate-plugin-ui-catalog.mjs
node frontend/scripts/generate-plugin-ui-catalog.mjs --check
```

## 属性和交互

支持 Radix 的颜色、尺寸、variant、radius、highContrast、as、asChild、布局、间距、宽高、对齐、栅格、文字属性等可序列化参数，以及输入、选项组、Slider、弹层的常用属性。响应式值按 Radix 形式传入：`{"size":{"initial":"1","md":"3"},"columns":{"initial":"1","sm":"2"}}`。支持 `className`、内联 `style`、`data-*`、`aria-*`。某个组件的有效值以目录为准；并非 React Props 都可序列化。

| 回调 | 传给后端的 value |
| --- | --- |
| `onPress` / `onClick` | null，event 为 press |
| `onInput` / 输入控件 `onChange` | 字符串，event 为 input |
| `onSubmit` | 输入字符串，event 为 submit |
| 选择器 `onChange/onSelect/onValueChange` | 所选值；多选为字符串数组 |
| `onCheckedChange` / Checkbox、Switch 的 `onChange` | boolean（Checkbox 可 indeterminate） |
| `onValueChange/onValueCommit`（Slider） | 数字数组；commit 在交互完成时发送 |
| `onOpenChange` | boolean |
| `onFocus/onBlur` | null |
| `onCommit`（StepperNumberInput） | 提交后的数字；onChange 为编辑字符串 |

所有回调都填写后端 action ID。不能传 React 函数、ref、DOM 节点或事件代码。`asChild` 要求恰好一个组件子节点，宿主会保留 Radix 的 ref、焦点和事件透传。Dialog 等复合组件需遵循 Radix 的结构及无障碍要求，如 Title 和 Description。错误组件树由局部错误边界显示，不应导致主应用崩溃。

旧版 `Box` 保留 Flex 的默认纵向布局和数值间距（每单位 4px，gap 限制为 0–8）；新插件建议使用 `Flex/Grid` 及 Radix 字符串间距（如 `gap="3"`）。`Input` 是 `TextField.Root` 别名，保留编辑草稿；`Code/Markdown` 保留预格式文本，不解析 Markdown。`Svg/Image/Client` 仅显示不支持提示。声明式视图按内容自然布局，对话输入框上方最高为 420px 或窗口高度的 45%，超出部分内部滚动。

## 自定义 CSS

文档顶层可返回 `css`（最大 64 KiB），组件通过 `className/style` 使用样式。支持普通选择器、CSS 变量、嵌套样式、media/supports/container 查询及 keyframes；内联样式支持 camelCase、kebab-case 和 `--custom-properties`。数值长度遵循 React 内联样式约定。

```python
return {
    "css": ".sync-card { padding: 16px; border: 1px solid var(--accent-7); } .sync-dialog { max-width: 480px; }",
    "tree": {"type": "Card", "props": {"className": "sync-card", "style": {"--card-gap": "8px"}}, "children": [
        {"type": "ModelSelector", "props": {"value": model_id, "onChange": "model"}},
        {"type": "Dialog.Root", "children": [
            {"type": "Dialog.Trigger", "children": {"type": "Button", "children": "设置"}},
            {"type": "Dialog.Content", "props": {"className": "sync-dialog"}, "children": [
                {"type": "Dialog.Title", "children": "同步设置"},
                {"type": "Dialog.Description", "children": "选择同步参数"}
            ]}
        ]}
    ]}
}
```

宿主使用 PostCSS 解析 CSS，并用 `postcss-nesting` 将嵌套样式展开为普通规则，再通过选择器 AST 将每条规则的匹配目标约束到当前视图根及其后代。输出不包含 CSS `@scope`，也不依赖 `CSSStyleSheet.replaceSync` 或浏览器原生 CSS nesting。约束使用已广泛支持的 `:where()`（Chrome/Edge 88、Firefox 78、Safari 14 起支持），保留原选择器的优先级。插件仍以 `UIDocument.css` 传入字符串，不需要改写插件或自行引入这些库。

`html`、`body`、`:root`、`:scope` 映射到插件根；常见的 `html > body` 根链合并为同一个根。选择器列表、函数伪类、兄弟组合符和伪元素也受到目标范围约束。Dialog、Select、Popover、Tooltip 和项目组件的弹层挂载至具有相同实例标识的 Portal 容器，保持项目弹层的原有交互。弹层不在触发器包装容器的 DOM 子树内；需要共享的 CSS 变量请定义在 `:scope`。

支持 `@media`、`@supports`、`@container` 和 `@keyframes`；具体条件及 CSS 属性仍取决于浏览器本身的支持。动画名称按视图实例重命名，同步处理样式表、内联样式及动画引用的 CSS 变量链；普通颜色变量不会因与动画同名而被重写。动画名称如果与 `linear` 等简写关键字重名，请使用 `animation-name` 或带引号的动画名称。

单个样式表最多 64 KiB、32 层嵌套、8192 个 AST 节点；展开后最多 2048 条规则、512 KiB。超出部分忽略并提示；语法损坏的样式表整段忽略，不会回退到未经处理的 CSS。处理结果按当前视图的 CSS 缓存，交互事件不会反复编译相同样式。

忽略 `@import`、`@font-face`、`@property`、输入中的 `@scope` 等未支持规则；过滤脚本 URL、expression 及旧式可执行属性。CSS 资源 URL 支持 HTTP/HTTPS 和部分 raster base64 图片。PostCSS 不下载资源、不加载插件提供的处理器，组件由宿主原生渲染。此边界限制选择器影响范围，宿主主题仍可影响插件；它不限制插件在自身节点使用 fixed 定位或大尺寸，也不是后端安全沙箱。

可安装示例：`examples/plugins/declarative-showcase`，展示项目组件、响应式 Grid、Tabs、Dialog、DropdownMenu、Popover、Tooltip、数组事件和样式。使用现有 `examples/plugins/build_package.py` 打包安装。

高级文档可以返回 `{trees, panes, commands}`：trees 每项包含 `{component, requestId, tree}`；panes 包含 `{id, title, focus, closeOnEscape}`；commands 包含 `{name}`。宿主用 requestId 关联 Pane，支持面板焦点、关闭和 Escape。快捷键只在当前插件区域持有焦点时响应，不截获 Agent 输入框或其他插件的输入。

## 校验边界

回调是后端识别的字符串 ID，不能传函数或代码。组件及属性采用白名单，树深度最多 32、节点最多 4096、文档最多 1 MiB，上下文与事件值各最多 64 KiB。事件排队执行，离开当前视图后放弃尚未发送的事件。事件命令由清单绑定，浏览器请求不能指定其他 RPC 方法。

前端只把协议字段映射到固定组件，样式按上述作用域处理，不注入 HTML，也不执行插件浏览器代码。链接在新窗口打开并禁止访问 opener。原生 Python 插件仍是可信后端代码，此 UI 协议不改变其后端执行权限。

## 原生插件

声明式协议是原生插件 SDK 的独立能力：Python 插件通过 `render`/`action` 命令提供组件树及交互处理，主应用使用 Radix 组件渲染。HTML、React、Vue 等预构建应用使用 iframe SDK。宿主已移除第三方 Mod 模块执行和格式转换。
