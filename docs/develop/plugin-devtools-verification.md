# 插件 Devtools 验证记录

验证日期：2026-10-20。功能说明和使用命令见 [插件 Devtools](./plugin-devtools.md)，可运行示例见 [devtools-demo](../../examples/plugins/devtools-demo/README.md)。本轮使用独立数据目录，没有操作用户数据库，也未推送分支。

## 结果

| 检查 | 结果 |
| --- | --- |
| 后端插件、Agent Runtime 和 CLI 回归 | 1,103 passed，9 skipped；164.82 秒 |
| 最终 Devtools 边界专项复验 | 6 passed；5.16 秒 |
| Playwright | 32 项独立用例通过：21 项浏览器端到端、11 项 CSS/effect 逻辑测试 |
| 前端生成物、类型感知 lint、tsc、生产构建、改动文件格式 | 通过 |
| 后端改动 Ruff | 通过 |
| 七个示例静态检查 | 全部通过；动态或未配置的检查仍按实际报告，不等同于都执行了 lint |
| devtools-demo 严格检查与 ZIP | CSS、Ruff、Oxlint、TypeScript 实际执行并通过；ZIP 10 个文件、7,712 字节，与源码逐字节一致，排除依赖和开发数据 |
| npm 包与正式 wheel | 打包成功；wheel 中新增模块、SDK 和全部前端文件与最终源码/构建逐字节一致 |

9 项跳过来自可选 PostgreSQL 环境和 Windows 专用检查，没有计入通过。生产构建保留已有的大 chunk 提示。前端总计增加 3 个资源文件、16,457 字节；全部 JS 按 gzip level 6 汇总增加 6,612 字节。开发工具页面按路由懒加载。

机器可读结果见 [plugin-devtools-results.json](./plugin-devtools-results.json)。截图、原始日志及示例 ZIP 保存在执行环境的 `/workspace/openfic-verification/plugin-devtools/`。主验证使用最终生产构建；编辑器权限网关专项按其测试设计使用 Vite。

## 测试范围

新增端到端测试直接启动 `openfic plugin dev`，使用生产构建的前端、真实 FastAPI、SQLite、安装器、源码监听器及 SDK。测试在一次性源码副本上修改文件，不改动仓库中的示例实现。

- 原生独立页面、工具栏 Popover、全局浮层，960/390px 视口、浅深主题、上下文校验。
- 组件树和 Props、原始/编译后 CSS、过滤提示、SDK 权限错误、测试密钥脱敏、清空及导出诊断。
- 修改 Python 后同版本更新、计数和配置保留；非法 Props 预检失败及 Python 激活异常均保留旧实现；修复后恢复。
- iframe 静态资源热重载、存储保留、主题上下文重新初始化，以及标准 CORS 脚本的详细 error 采集。

后端新增测试还验证普通实例默认关闭 Inspector、认证路由的插件身份校验、记录条数上限、提交后观察事件、SDK 直接调用与前端报告两种来源的脱敏、失败的 secret 写入、离线检查不执行插件代码也不创建应用数据、严格检查与打包门禁，以及忽略依赖/开发数据目录。

现有回归覆盖项目统计、独立 React/iframe 插件、Google Drive 同步与 Agent 工具、Handoff Graph、动态提示词、原生示例、项目选择器的移动端 Sheet、Radix 事件和 Portal、CSS 隔离、编辑器工具栏、小鲸鱼浮层、普通导航及设置。章节和笔记另按插件未安装、停用、启用三种状态验证编辑、保存、切换和 SDK 权限边界。

## 复现

```bash
cd backend
uv run pytest tests/plugins tests/agent_runtime tests/test_cli.py -q
uv run python -m app.cli plugin check ../examples/plugins/devtools-demo --run-checks --strict --json
uv run python -m app.cli plugin pack ../examples/plugins/devtools-demo --output /tmp/devtools-demo.zip --run-checks --strict
cd ../frontend
pnpm type-check
pnpm exec tsc -b
pnpm build
```

浏览器新用例需要真实开发服务和一次性源码副本，设置 `OPENFIC_E2E_BACKEND`、`OPENFIC_E2E_BASE_URL` 及 `OPENFIC_E2E_PLUGIN_SOURCE` 后运行 `playwright test e2e/plugin-devtools.spec.ts`。原有插件回归使用 `tests.plugins.whale_e2e_app:app` 提供外部协议仿真；`writing-regression.spec.ts` 通过 Vite 开发服务导入前端权限网关。浏览器测试期间不可重建其正在读取的静态资源。

## 边界

测试使用 Linux/Chromium，没有运行原生 Windows/macOS 安装程序或 PostgreSQL 集成环境。Google Drive、DeepSeek 和模型请求使用测试专用协议仿真；未连接真实云账号或付费模型。

静态检查不会求值动态 Python/UI 表达式，也不会证明所有 action 分支均有实现。插件前端的真实 lint/type-check 通过作者自己的配置执行；没有执行或没有配置时明确报告。开发预览使用同源宿主 iframe 隔离视口，生产声明式 UI 继续原生渲染。

诊断默认关闭，仅保留有条数和载荷上限的内存记录，不是审计日志。脱敏覆盖声明的 secret 设置、已读取 secret 值与常见敏感字段；其他正文或业务内容仍可能出现在报告中。Python 插件仍是可信代码，独立开发数据目录不提供执行沙箱。
