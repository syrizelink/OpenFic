# 原生插件与 Claude Mods 移除验证

验证日期：2026-10-19。此记录对应移除 Claude Mods 兼容支持后的代码；此前的 SDK 和回归报告保留为历史记录。

## 改动范围

删除 Mod 包转换、版本迁移、JS/TS/JSX 执行器、Claude 事件翻译、QuickJS 依赖、Sucrase 转换器及其专用测试、fixture、截图。插件管理与渲染界面去掉兼容信息和格式判断，测试提供商也删除专用于官方 Mods 的分支。

保留原生插件生命周期、完整 SDK、Agent 工具/hooks/Graph、编辑器接口、全部通用插槽、iframe 应用和宿主 Radix 声明式 UI，以及项目统计、Google Drive、Handoff 和动态提示词示例。此前修复的 Agent 和编辑器回归保留。

## 安装与已有数据

- 原生 ZIP 必须在根目录提供 `plugin.json`；省略 `format` 或使用 `openfic`。
- 原始 Mod ZIP 和此前生成的 `format: "claude-mod"` 包均返回 400，不执行代码，不影响其他原生插件。
- 启动遇到磁盘上已安装的旧 Mod 时，记录错误并跳过；其目录和持久化数据不自动删除，其他原生插件继续加载。
- 旧原生导出包中的 `compatibility` 元数据仍可读取，但不再由管理接口输出。导出继续保留插件包内原始文件，不重写用户源码。

## 验证

最终结果见 [plugin-native-results.json](./plugin-native-results.json)。原始日志、JUnit、构建包和专用测试数据位于 `/workspace/openfic-verification/mod-removal/`。

| 检查 | 结果 |
| --- | --- |
| 后端全量 | 2314 passed、19 条件跳过，313.44 秒 |
| 原生插件专项（全量的子集） | 53 passed |
| 生产构建浏览器 | 6 个不同场景最终通过 |
| Ruff、ty、前端格式/类型和 E2E 类型/lint | 通过 |
| 前端构建、wheel、锁文件一致性 | 通过；环境与分发包均无 QuickJS |

首轮浏览器为 5 passed、1 failed：导航用例依赖已有项目数据，空库下角色查询不会执行。已改为创建并清理临时项目，在页面查询完成后切换路由；单项复验通过。`browser-before-shell-fix.xml`、失败 trace 和 `browser-shell.xml` 均保留，按同名场景的最终结果统计，不删除早期失败记录。浏览器后端日志没有 HTTP 500。

插件专项验证生命周期、原生业务 SDK、工具/提示词中间件、声明式渲染、示例与旧包拒绝。其中旧包测试覆盖原始 ZIP、带一层目录的 ZIP、旧转换 ZIP；另验证启动不执行旧包代码且保留数据、旧原生导出包仍可正常重启加载。

浏览器使用生产静态构建、真实应用/SQLite/Socket 和安装接口，验证原生声明式与 iframe 混合渲染、Google Drive OAuth/冲突与 Agent 同步工具、Handoff、动态提示词与编辑器保存、React SDK 插件、项目统计完整生命周期，以及管理 UI 拒绝原始和旧转换 Mod 包后仍可安装原生插件。另验证全局导航、设置与移动端布局。

Google Drive 和模型提供商使用本地协议仿真；没有使用真实 Google 账号、付费模型或原生桌面安装程序。本轮未重跑 PostgreSQL 专项；此前的数据库专项记录见 [历史回归报告](./plugin-regression-verification.md)。

wheel 使用独立打包目录和已构建前端资源，检查 Mod 运行时/转换器不在包中、元数据没有 QuickJS 依赖、所有原生插件源文件与当前代码相同。测试虚拟环境中也实际卸载了 QuickJS。

## 复现

```bash
cd backend
uv sync --locked --extra postgresql
uv run ruff check . ../examples/plugins
uv run ty check app
uv run pytest -q -ra
```

启动隔离后端：

```bash
cd backend
OPENFIC_DATA_DIR=/tmp/openfic-native-verification OPENFIC_AUTH_PASSWORD= \
  uv run uvicorn tests.plugins.e2e_app:app --host 127.0.0.1 --port 8021
```

先构建前端，再启动静态预览；浏览器运行期间保持构建目录不变：

```bash
cd frontend
pnpm format:check
pnpm type-check
pnpm build
OPENFIC_E2E_BACKEND=http://127.0.0.1:8021 OPENFIC_E2E_PREVIEW_PORT=9022 \
  node e2e/serve-plugin-preview.mjs
```

另一个终端执行：

```bash
cd frontend
OPENFIC_E2E_BASE_URL=http://127.0.0.1:9022 \
OPENFIC_E2E_BACKEND=http://127.0.0.1:8021 \
  pnpm exec playwright test e2e/app-shell-regression.spec.ts \
  e2e/declarative-plugins.spec.ts e2e/plugin-sdk.spec.ts e2e/plugins.spec.ts
```

系统 Chromium 可通过 `OPENFIC_E2E_CHROMIUM_PATH` 指定。
