# 原生插件 UI、CSS 与 SDK 增强验证

本文记录 `73bf598` 的历史验证；CSSOM / `@scope` 实现已由后续 [PostCSS 改造](./plugin-css-postcss-verification.md) 替换，当前用法见 [声明式 UI 文档](./declarative-plugin-ui.md)。

验证日期：2026-10-19，分支 `feat/extension-host`，基于移除 Mods 后的 `5dafe68`。本轮保留 Mod 拒绝逻辑，没有恢复兼容运行时。

## 交付内容

- 共享生成目录：122 个 Radix Themes 组件及子组件入口、10 个项目组件；项目组件优先，提供 `Radix.*`、`Project.*` 显式名称。
- 复用真实模型/项目选择器、搜索选择、单位输入、数字步进、Spinner、进度和 Tooltip；数据经已有 SDK 网关和能力校验读取。
- 扩展颜色、variant、尺寸、响应式布局、复合组件、受控状态和字符串/布尔/数组事件；目录同时由 HTTP、SDK RPC 和公开 TypeScript 类型提供。
- 自定义 CSS 经 CSSOM 解析并按视图 `@scope`；项目及 Radix 弹层进入对应 Portal，动画名称按实例隔离。支持内联样式、CSS 变量、嵌套规则及条件查询，限制深度/规则数，过滤不支持的全局规则及危险值。
- 可直接安装 [展示插件 ZIP](../../examples/plugins/dist/declarative-showcase-1.0.0.zip)，源码见 [示例](../../examples/plugins/declarative-showcase/README.md)，协议见 [使用文档](./declarative-plugin-ui.md)。

## 最终结果

| 检查 | 结果 |
| --- | --- |
| 后端全量 `pytest -q` | **2330 passed、19 skipped**，348.44 秒 |
| 插件专项 `pytest tests/plugins -q` | **69 passed** |
| 生产构建浏览器回归 | **8 passed、0 failed** |
| 前端 type-aware 检查、`tsc -b` | 通过；包含不依赖 React 的 SDK 类型消费样例 |
| 前端 Lint、改动文件格式、Python Ruff | 通过 |
| 组件目录及两份 SDK 类型的新鲜度/一致性 | 通过，已接入前端 type-check |
| 前端生产构建 | 通过 |
| 发行 wheel | 通过；组件目录、SDK 类型及 740 个前端文件与最终源文件/构建逐字节一致 |

浏览器使用真实应用、生产静态资源、SQLite、Socket、安装/启用/卸载及 SDK 接口。新增展示插件实际完成模型/项目读取与选择、单位输入、步进提交、搜索选择、多选数组、Slider 数组、原生 Select 标签、Radio、Tabs、Dialog 的 Escape 和焦点恢复、菜单、Popover、两种 Tooltip、重载持久化；桌面和移动端均有覆盖。

样式验证包括响应式 Grid、嵌套 media 声明、Code 属性/内联样式、弹层边框、多视图同名类及动画隔离、宿主按钮/正文不受插件选择器影响，以及危险 URL、全局规则、超深 CSS 的处理。显式 `aria-label` 优先于旧 `label` 别名，复杂项目组件保留 `data-*`、`aria-*` 等属性。

原有回归包括导航、设置插件分类、移动布局、原生/iframe 混合视图、React SDK 插件、项目统计安装/配置/停用/卸载，以及 Drive OAuth/冲突/Agent 手动工具、handoff Graph、动态提示词和编辑器保存。已移除的原始及旧转换 Mod 包仍被拒绝。

## 验证边界与复现

19 条后端测试按数据库/平台条件跳过，本轮未另行启动这些条件环境。浏览器覆盖 Chromium 及移动视口，未启动真实 Tauri 安装窗口；CSS 依赖浏览器/WebView 支持 `@scope`，不支持时保留组件交互并提示样式不可用。Drive 和 LLM 使用仓库提供的协议替身，未连接真实 Google 账号。

组件生成与验证：

```sh
node frontend/scripts/generate-plugin-ui-catalog.mjs --check
cd backend
.venv/bin/pytest -q
.venv/bin/pytest tests/plugins -q
cd ../frontend
npm run type-check
./node_modules/.bin/tsc -b
npm run lint
npm run build
```

浏览器需先启动独立 `tests.plugins.e2e_app:app`、设置可丢弃的 `OPENFIC_DATA_DIR`，再用 `e2e/serve-plugin-preview.mjs` 服务最终 dist；等待 health 就绪后运行 `declarative-showcase`、`declarative-plugins`、`plugin-sdk`、`plugins`、`app-shell-regression` 五个 spec。使用 `OPENFIC_E2E_BACKEND/BASE_URL/CHROMIUM_PATH` 指向这些实例。

机器可读结果见 [plugin-ui-results.json](./plugin-ui-results.json)。原始日志、JUnit 和 wheel 核验位于 `/workspace/openfic-verification/ui-enhancement/`。此前失败的调试轮次未计入最终通过结果；最终八项在同一生产构建上完整重跑通过。
