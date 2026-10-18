# SDK 2.0 验证记录

2026-10-18 追加了官方仓库全部三个 Mod 的原包安装和浏览器验证，并修复实际兼容缺口。逐项结果、限制和复现见 [官方 Mods 报告](./claude-mods-compatibility.md)。下表保留 2026-10-17 SDK 交付时的历史记录。

验证日期：2026-10-17。测试使用隔离数据目录，不连接用户数据库。安装包见 `examples/plugins/dist/`，源码与操作说明见 [示例插件](./plugin-examples.md)，接口与限制见 [SDK 2.0](./plugin-sdk-v2.md)。

最终结果：

| 检查 | 结果 |
| --- | --- |
| 后端全量 pytest | 2286 passed、19 skipped，253.05 秒 |
| 插件、React Agent、工具基础专项回归 | 75 passed |
| Chromium 端到端 | 4 passed，约 1.6 分钟 |
| 后端 Ruff、ty | 通过 |
| 前端格式、lint、类型检查及 E2E TypeScript 检查 | 通过 |
| 生产前端与正式 wheel 构建 | 通过；核对内嵌资源及最终 Agent SDK 源码 |
| 独立 SDK npm pack、三个示例 ZIP | 打包、完整性检查通过 |
| 三个插件独立页面 | 实际浏览器打开、截图并人工检查布局 |

19 项跳过沿用测试环境条件，包括 PostgreSQL 等可选环境；没有把跳过项目计作通过。生产构建保留现有的较大 chunk 提示，不影响构建成功。

## 自动化范围

后端插件测试覆盖原有生命周期、更新失败回滚、认证、静态资源票据、业务 CRUD 与能力校验、JSON/文件/密钥存储、网络白名单、事件顺序与重入、编辑器读写权限、工具注册、Graph 选择、Mod continuation、TSX 转换及 CPU/Node 导入边界。

三个示例分别验证：

- Drive：OAuth PKCE 与一次性 state、令牌刷新、上传/下载、分页、去重、双端冲突与显式解决、Agent 手动上传工具。
- Handoff：演示与模型路径、LangGraph `Command` 交接、项目 Graph 选择与恢复、工具调用和结果成对持久化、保存笔记。
- 提示词：规则匹配、元素开关、消息注入/替换/移除、系统片段控制、项目覆盖、实际 Agent 模型请求中的注入。

浏览器使用生产构建的静态前端、真实业务后端和 SQLite，经过登录和管理 UI 安装、启用插件，在 iframe 中操作。四个 Playwright 用例覆盖：

1. 三个示例的组合流程：OAuth 回调及重放拒绝、Drive 冲突解决、原生 Agent 的插件工具、真实会话中的 Handoff Graph、提示词注入、编辑器插入并保存、移动端布局。
2. 原始 Claude TSX Mod ZIP 的直接安装、命令、UI 渲染和按钮状态更新。
3. 真正由 React 构建并导入独立 SDK 包的插件：样式、KV 重载持久化、未声明能力拒绝。
4. 原有项目统计插件的安装、配置、更新、停用、导出、卸载回归。

嵌套内置 Agent 工具另有回归测试，检查审批接收实际内层参数、保留 revision 和外层调用身份、移除外层跳过审批标记，并避免重复模型回调。

## 复现

后端：

```bash
cd backend
uv run ruff check . ../examples/plugins
uv run ty check app
uv run pytest -q
```

前端：

```bash
cd frontend
pnpm format:check
pnpm lint
pnpm type-check
pnpm exec tsc --noEmit --target ES2022 --module ESNext --moduleResolution Bundler \
  --jsx react-jsx --esModuleInterop --skipLibCheck e2e/plugin-sdk.spec.ts e2e/plugins.spec.ts
pnpm build
```

浏览器后端/预览服务和测试环境变量见 [示例插件的本地验证](./plugin-examples.md#打包与本地验证)。不要在浏览器用例运行时重新构建前端，构建会替换预览服务正在读取的静态文件。

独立 SDK 可以在 `packages/plugin-sdk` 执行 `npm pack`，类型声明与后端分发的 `sdk.d.ts` 保持一致。正式 wheel 的构建链也经过验证，检查 wheel 内含 SDK JS/声明、Mod runtime/view、Sucrase 转换器与第三方许可证，以及前端生产资源。

## 实际验证边界

Google OAuth/Drive 和模型提供商使用本地协议仿真；业务应用、宿主、数据库、权限检查、消息桥和 Agent 执行链使用真实代码。未使用真实 Google 账号授权或真实付费模型，真实云同步仍需要部署者配置自己的 Google OAuth 客户端。

本次验证没有运行 Windows/macOS/Linux 原生桌面安装程序，也没有运行 PostgreSQL 专用集成环境。原生 Python 插件属于可信代码，仍未进行进程沙箱隔离。Claude Mods 属于文档所列子集兼容，不保证所有第三方 Mod 无修改运行。
