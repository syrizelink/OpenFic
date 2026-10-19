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

## 组件和布局

| 节点 | 渲染与事件 |
| --- | --- |
| `Box/Text` | Radix Flex/Text，方向、对齐、主题色、粗体、淡化和间距 |
| `Button` | Radix Button，`onPress`、禁用、焦点和局部快捷键 |
| `Input` | Radix TextField，`onInput/onSubmit`，保留输入草稿 |
| `Select` | Radix Select，`options`、`onSelect` |
| `Checkbox/Switch` | Radix Checkbox/Switch，`checked`、`onChange` |
| `Link` | Radix Link，只允许 HTTP/HTTPS |
| `Badge/Separator/Progress` | Radix 对应组件，Progress 的 value 为百分比 |
| `Code/Markdown` | 安全的预格式文本；当前不解析 Markdown 语法 |
| `Svg/Image/Client` | 显示不支持提示，不加载脚本、资源或外部组件 |

加载状态复用项目 Spinner。宿主不开放任意 HTML 标签、CSS、组件导入或组件内部实例。间距单位为 4px，数值限制为 0–8；颜色映射到项目主题变量。声明式视图按内容自然布局，对话输入框上方最高为 420px 或窗口高度的 45%，超出部分内部滚动；不需要 iframe 的 `ui.resize`。

高级文档可以返回 `{trees, panes, commands}`：trees 每项包含 `{component, requestId, tree}`；panes 包含 `{id, title, focus, closeOnEscape}`；commands 包含 `{name}`。宿主用 requestId 关联 Pane，支持面板焦点、关闭和 Escape。快捷键只在当前插件区域持有焦点时响应，不截获 Agent 输入框或其他插件的输入。

## 校验边界

回调是后端识别的字符串 ID，不能传函数或代码。组件及属性采用白名单，树深度最多 32、节点最多 4096、文档最多 1 MiB，上下文与事件值各最多 64 KiB。事件排队执行，离开当前视图后放弃尚未发送的事件。事件命令由清单绑定，浏览器请求不能指定其他 RPC 方法。

前端只把协议字段映射到固定组件，不展开任意属性，不注入 HTML/CSS，也不执行插件浏览器代码。链接在新窗口打开并禁止访问 opener。原生 Python 插件仍是可信后端代码，此 UI 协议不改变其后端执行权限。

## 原生插件

声明式协议是原生插件 SDK 的独立能力：Python 插件通过 `render`/`action` 命令提供组件树及交互处理，主应用使用 Radix 组件渲染。HTML、React、Vue 等预构建应用使用 iframe SDK。宿主已移除第三方 Mod 模块执行和格式转换。
