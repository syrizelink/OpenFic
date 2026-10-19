# 声明式 UI PostCSS 改造验证

验证日期：2026-10-19；分支 `feat/extension-host`，基于 `73bf598`。此轮替换自定义 CSS 的处理方式，插件接口和可安装示例保持兼容。

## 改造结果

- PostCSS 解析 CSS；postcss-nesting 展开嵌套；选择器 AST 将匹配目标限制到当前视图及其 Portal 容器，输出普通 CSS，不使用 `@scope`。
- `html`、`body`、`:root`、`:scope` 映射为实例根，处理选择器列表、根链、兄弟关系、函数伪类及伪元素。范围约束使用成熟的 `:where()`，不会额外增加匹配目标的选择器优先级。
- 动画按实例命名，同步处理简写、animation-name、内联样式、CSS 变量链、引号及转义。资源值解析和规则预算在宿主处理；损坏的 CSS 不会回退为未经约束的原文。
- 插件继续传入 `UIDocument.css`；无需修改插件包。现有项目及 Radix 组件仍通过原生 DOM 渲染。

## 本轮结果

| 检查 | 结果 |
| --- | --- |
| PostCSS 编译专项 | **6 passed**，在没有 window/CSSOM 的 Node 环境运行 |
| 生产构建浏览器回归 | **9 passed**，Chromium 桌面及移动视口 |
| 插件后端 `pytest tests/plugins -q` | **69 passed**，10.07 秒 |
| type-aware、`tsc -b`、Lint | 通过 |
| 改动前端文件格式、diff 空白检查 | 通过 |
| 组件目录与 SDK 类型新鲜度 | 通过，122 个 Radix 入口、10 个项目组件 |
| 生产构建、离线 frozen-lockfile 核验 | 通过 |
| wheel 打包 | 通过，740 个前端文件逐字节匹配构建；目录和 SDK 类型匹配源码 |

编译专项覆盖嵌套与条件规则、动画列表和变量链、普通颜色变量、转义及引号、全局注册规则、URL 和内联属性过滤、损坏输入及深度/规则数预算。独立浏览器样式用例覆盖输入框、textarea、伪元素、根链、Portal、多实例及试图通过兄弟选择器和函数伪类匹配宿主节点的样式。

原生展示插件测试在加载前将 `CSSScopeRule` 设为 undefined，并使 `CSSStyleSheet.replaceSync` 抛错，随后实际安装、启用插件，验证样式、动画、模型/项目选择器、响应式布局、Dialog、菜单、Popover、Tooltip、焦点恢复及重载持久化。移动端选择器及弹层另有回归。

其余回归覆盖原有导航和移动布局、原生与 iframe 混合插件、React SDK 插件、项目统计安装/配置/停用/卸载，以及 Drive OAuth/冲突/Agent 工具、handoff Graph、动态提示词和编辑器保存。已移除的 Mod 包仍被拒绝。

## 复现与边界

```sh
cd frontend
npm run type-check
./node_modules/.bin/tsc -b
npm run lint
npm run build
npm run test:plugin-css
cd ../backend
.venv/bin/pytest tests/plugins -q
```

应用回归需启动使用独立 `OPENFIC_DATA_DIR` 的 `tests.plugins.e2e_app:app`，等待 health 就绪，使用 `frontend/e2e/serve-plugin-preview.mjs` 服务最终 dist，再运行以下六个 spec：`declarative-css`、`declarative-showcase`、`declarative-plugins`、`plugin-sdk`、`plugins`、`app-shell-regression`。使用 `OPENFIC_E2E_BACKEND/BASE_URL/CHROMIUM_PATH` 指向测试实例。

本轮通过的是 Chromium 与 API 缺失模拟，没有实际启动旧版 Safari、Firefox、系统 WebView 或 Tauri 窗口；具体 CSS 属性与条件查询仍取决于浏览器支持。Drive、LLM 使用仓库协议替身。本轮没有重跑后端全量；此前 2330 passed / 19 skipped 属于上一轮历史验证，不计入本轮结果。

机器可读结果见 [plugin-css-postcss-results.json](./plugin-css-postcss-results.json)，当前协议见 [声明式 UI 文档](./declarative-plugin-ui.md)。原始日志、JUnit XML、wheel 和字节核验位于 `/workspace/openfic-verification/postcss/`，编译、安装及后端日志位于同级 `postcss-*.log`。
