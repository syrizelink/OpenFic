# 扩展宿主与插件开发（包 API v1 / SDK 2.0）

新增完整业务访问、编辑器操作、多个插槽、Agent 工具/中间件/Graph 与 Claude Mods 兼容，见 [SDK 2.0](./plugin-sdk-v2.md) 和 [三个示例插件](./plugin-examples.md)。下文保留最小项目统计包示例。

OpenFic 使用统一 ZIP 插件包。插件安装在当前连接的后端实例的 `OPENFIC_DATA_DIR/plugins/` 中；前端由内嵌的扩展宿主动态加载插件资源，不需要重新构建主应用。桌面版同样使用运行时配置中的后端地址。

## 安装项目统计插件

仓库提供可安装包 `examples/plugins/dist/project-statistics-1.0.0.zip` 和完整源码。重新打包：

```bash
python examples/plugins/build_package.py examples/plugins/project-statistics examples/plugins/dist/project-statistics-1.0.0.zip
```

1. 打开侧栏独立「扩展」区域的「插件管理」，或设置中的「插件管理」。
2. 阅读可信代码说明，勾选来源确认，点击「安装插件包」，选择 ZIP。
3. 安装后默认停用。点击「启用」后，扩展区域出现「项目统计」。
4. 打开独立页面，选择项目。统计包含已保存的章节、卷、角色、项目世界书条目和笔记。
5. 在管理页面的「插件配置」中设置目标字数和是否显示卷统计。保存后重新打开插件页面即可应用。

统计使用章节记录的字数，与应用的保存口径一致；未保存的浏览器工作副本不计入。空项目、空章节和零字数可正常展示。

管理支持 ZIP 安装、版本更新、启用、停用、配置、最近 200 条生命周期/错误日志、安装包导出和确认卸载。停用后服务端命令与资源访问立即失效，其他前端在刷新插件列表后移除入口。配置和启用状态在重启后保留。卸载删除插件代码和配置，生命周期日志单独保留以便排查。

## 包格式

ZIP 根目录必须直接包含 `plugin.json`，而非多套一层项目目录。前端文件必须已经构建；后端入口是 Python 文件。当前不自动执行 pip/npm 安装。

```text
plugin.json
backend/main.py
frontend/index.html
frontend/app.js
frontend/style.css
```

```json
{
  "id": "my-plugin",
  "name": "My plugin",
  "version": "1.0.0",
  "api_version": 1,
  "backend": "backend/main.py",
  "capabilities": ["projects.read", "project.entities.read"],
  "views": [
    {
      "id": "overview",
      "title": "My view",
      "entry": "frontend/index.html",
      "slot": "sidebar.extensions"
    }
  ],
  "settings": [
    {"key": "target", "label": "Target", "type": "integer", "default": 100, "minimum": 1}
  ]
}
```

`backend` 可省略，支持纯 UI 包；`views` 可以为空，支持纯后端包。ID、版本、入口和设置在安装时严格验证。压缩包上限 20 MiB、展开内容上限 40 MiB、最多 512 个条目；拒绝路径穿越、符号链接、重复路径、加密包和缺失入口。

更新使用「更新安装包」，包 ID 必须匹配，版本必须严格递增。安装更新时保留仍存在的设置与启用状态。新版本激活失败，会恢复旧代码、配置和命令。临时目录和目录交换的备份支持启动时清理/恢复。

## 后端 SDK

入口导出 `register(host)`，可同步或异步执行。`host.register_command(name, handler)` 注册插件命名空间内的命令，不会覆盖其他插件或内置业务接口。处理函数接收请求级 `PluginContext` 与参数：

```python
from app.plugins import PluginContext

async def list_projects(context: PluginContext, params: dict):
    return await context.data.list_projects()

def register(host):
    host.register_command("projects.list", list_projects)

async def deactivate():
    # 可选：关闭插件自己创建的资源。
    pass
```

Context 包含宿主绑定的 `plugin_id`、当前设置快照和数据接口：

- `data.list_projects()`：项目 ID/title DTO，要求 `projects.read`。
- `data.project_entities(project_id)`：项目及章节、卷、角色、笔记、世界书条目的元数据 DTO，要求 `project.entities.read`。不暴露 ORM session，不返回正文，不包含其他项目实体。

插件自己进行统计聚合。配置在命令执行时读取，因此无需重启。普通命令 RPC 参数最大 64 KB，SDK 方法参数最大 4 MiB，返回值必须可 JSON 序列化，最大 4 MiB；异步命令超时 120 秒。启停和更新等待正在执行的命令完成，避免旧实现执行时被移除。错误记录到插件日志并返回可展示的错误响应。

## 前端 SDK 与插槽

SDK 2.0 提供多个 UI 插槽；以下以 `sidebar.extensions` 和独立页面宿主为例。插件页面在 `sandbox="allow-scripts"` 的 iframe 中运行，不能直接操作主页面 DOM、应用 cookie 或编辑器。资源响应 CSP 禁止页面直接发起网络请求；UI 通过消息桥调用本插件后端命令。

位于 `frontend/index.html` 的页面可以这样加载公共 SDK：

```html
<script src="../../sdk.js" defer></script>
<script src="./app.js" defer></script>
```

```javascript
OpenFic.ready.then(async (context) => {
  // context: pluginId, projectId, language, theme, settings
  const projects = await OpenFic.call("projects.list", {});
  // 用插件自己的 UI 框架或原生 DOM 渲染 projects。
});
```

宿主校验 iframe 窗口来源、opaque origin、每次挂载的随机 channel 和消息格式。宿主固定 RPC 的插件 ID，插件不能通过消息选择调用其他插件。关闭页面会清理监听器，并忽略已关闭页面的迟到响应。框架无需与 OpenFic React 版本绑定。

隔离 iframe 的资源请求不依赖登录 cookie。已认证的前端先申请 15 分钟的随机静态资源票据，再打开 `/plugin-assets/{ticket}/...`。票据仅能读取指定插件的前端资源和公共 SDK，不能调用 RPC 或管理 API；停用、更新和卸载会撤销票据。资源使用 no-store 与 no-referrer，宿主访问日志不记录票据值。到期后重新打开页面即可申请新票据。

从项目页面打开插件时携带项目上下文；从全局打开时插件自行提供项目选择。主应用和示例 UI 支持移动布局，语言和主题在打开时传入。管理列表每五秒检查状态，使多窗口中的启停可见。

## 管理 API

路径相对于后端 API 前缀，遵守应用现有密码认证规则：

| 方法/路径 | 功能 |
| --- | --- |
| `GET /plugins` | 当前安装列表与状态 |
| `POST /plugins` | multipart：`file` ZIP、`trusted=true`；安装后停用 |
| `PUT /plugins/{id}/package` | 同格式更新 |
| `GET /plugins/{id}/package` | 导出安装包，不包含配置/日志 |
| `PATCH /plugins/{id}/enabled` | `{ "enabled": true }` |
| `PUT /plugins/{id}/settings` | `{ "settings": { ... } }` |
| `GET /plugins/{id}/logs` | 最近日志 |
| `DELETE /plugins/{id}` | 卸载 |
| `POST /plugins/{id}/rpc` | `{ "method": "name", "params": {} }` |
| `POST /plugins/{id}/views/{viewId}` | 申请仅限静态资源的短期视图地址 |
| `GET /plugins/{id}/assets/{path}` | 已启用插件的前端资源 |

安装权限沿用应用当前的共享密码模式；不是新增多租户权限系统。

## 执行边界与后续扩展

本版后端是**可信 Python 进程内插件**，不是安全沙箱。能力声明限制 SDK 可调用的方法，但无法阻止 Python 代码自行访问进程可达的文件、网络或内部模块。异步超时也不能强制终止阻塞的 Python 代码。只安装可信包。

SDK 2.0 已开放业务读写、多个 UI 插槽、存储/密钥/文件/网络、编辑器操作、Agent 工具与中间件和自定义 Graph。详细能力、兼容边界、调用限制见新文档；进程级隔离执行器仍未实现。

## 验证

后端测试覆盖真实包安装、统计值、配置校验、重启恢复、更新回退、命令清理、导出/卸载、路径校验、能力限制和密码认证：

```bash
cd backend
uv run pytest tests/plugins/test_host.py
```

浏览器测试通过真实管理 UI 上传 ZIP，验证独立页面、统计值、配置生效、刷新、停用、日志、卸载和移动视口。使用专门测试实例，避免删除用户已安装的同名统计插件：

```bash
cd frontend
OPENFIC_E2E_BASE_URL=http://127.0.0.1:9000 \
OPENFIC_E2E_BACKEND=http://127.0.0.1:8000 \
pnpm exec playwright test e2e/plugins.spec.ts
```

密码保护实例可设置 `OPENFIC_E2E_PASSWORD`；本机 Chromium 可通过 `OPENFIC_E2E_CHROMIUM_PATH` 指定。测试使用项目临时数据，并在结束时清理。

本次实现已验证：后端插件及认证、访问日志、应用启动回归共 34 项通过；Python/TypeScript 类型检查、lint 和生产构建通过；密码保护下的完整浏览器流程通过。浏览器流程同时在开发服务器和构建后的静态前端上运行，静态前端通过运行时配置连接独立后端，安装插件无需重新构建前端。未运行原生桌面安装包。
