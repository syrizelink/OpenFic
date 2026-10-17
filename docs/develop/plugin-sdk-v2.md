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
