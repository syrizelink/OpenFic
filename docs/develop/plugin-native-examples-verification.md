# 四个示例插件的声明式 UI 迁移验证

验证日期：2026-10-20；分支 `feat/extension-host`，基于 `ddbe34b`。

## 安装包与界面

四个示例升级为 **1.1.0**，共 **7 个声明式视图**。包内只包含清单和 Python 源码，已删除原来的 HTML、JS、CSS 前端文件。通过管理页「更新安装包」可从 1.0.0 升级；设置和插件数据继续保留。需要包含本轮声明式宿主操作支持的 OpenFic。

| 插件 | 安装包 | UI 入口和效果 |
| --- | --- | --- |
| 项目统计 | [project-statistics-1.1.0.zip](../../examples/plugins/dist/project-statistics-1.1.0.zip) | 侧栏独立页面；原生项目选择器、8 个统计卡片、目标进度、卷分布表；移动端两列卡片 |
| Google Drive | [google-drive-sync-1.1.0.zip](../../examples/plugins/dist/google-drive-sync-1.1.0.zip) | 侧栏页面和编辑器工具栏；连接状态、加密令牌导入、方向选择、变化预览、原生冲突确认弹窗、保存后同步 |
| Handoff | [handoff-workflow-1.1.0.zip](../../examples/plugins/dist/handoff-workflow-1.1.0.zip) | 侧栏页面；项目与模型选择器、任务输入、交接记录、结果、笔记保存、导出及项目 Graph 切换 |
| 动态提示词 | [prompt-elements-1.1.0.zip](../../examples/plugins/dist/prompt-elements-1.1.0.zip) | 侧栏规则页面、对话输入框上方开关、编辑器工具栏；JSON 草稿、规则预览、配置导出、读取/插入保存/撤销 |

控件复用现有项目组件及 Radix Themes，布局使用响应式属性和由宿主 PostCSS 处理的 CSS。页面不使用 iframe。声明式 action 的 `UIActionResult.effects` 通过现有前端 SDK 桥顺序执行编辑器和浏览器操作，保留能力检查、编辑器锁、视图生命周期及调用预算；普通 render 不执行这些操作。协议和限制见 [声明式 UI 文档](./declarative-plugin-ui.md)。

Python `context.call` 复用公共后端 SDK 分发器，用于项目 Graph 选择等操作。OAuth 回调发送 UI 刷新事件，使连接状态自动更新。项目内提示词开关复制配置后再保存，避免修改全局或其他项目的默认元素；不合法 JSON 草稿仍可继续编辑。

## 最终结果

| 检查 | 结果 |
| --- | --- |
| 插件后端回归 | **78 passed**，5.31 秒 |
| 生产构建浏览器回归 | **13 passed**，包含四个插件的桌面和移动操作 |
| CSS 编译与声明式宿主操作逻辑 | **11 passed** |
| 上述完整回归 | **24 passed、0 failed**；随后 OAuth 完整链路又专项 **1 passed** |
| type-aware、`tsc -b`、SDK 类型消费 | 通过 |
| Lint、Ruff、改动文件格式、diff 空白检查 | 通过 |
| 组件目录和两份 SDK 类型新鲜度 | 通过 |
| 最终生产构建、wheel | 通过；wheel 内 740 个前端文件、宿主 OAuth/SDK 代码及目录/类型逐字节匹配 |
| 四个 ZIP | 清单均为 1.1.0、全部视图声明式、无 frontend 资源、包内容逐字节匹配源码 |

业务验证通过真实管理 UI 安装/启用插件，覆盖统计与配置变化、OAuth 按钮及回调后自动更新连接状态、令牌导入后清空密码框、Drive 预览/同步/冲突确认与下载结果、Agent 手动同步、真实模型协议下的 Handoff、原生 Agent Graph、保存笔记、提示词预览及实际请求注入、读取编辑器、插入保存、撤销、编辑器保存后同步、输入框上方元素开关，以及导出文件。移动端在 390×844 重新加载并实际操作按钮，同时检查横向溢出；统计卡片从桌面 4 列变为 2 列。

后端新增覆盖旧 iframe 统计包升级后保留设置/启用状态、令牌草稿加密且不读回、错误 JSON 草稿不损坏已保存配置、Python SDK 能力检查，以及一个项目的开关不修改全局和另一个项目。原有 iframe 票据/CSP 生命周期测试继续使用独立的最小 legacy 视图，真实声明式安装由新增示例测试覆盖。

原有应用导航、移动布局、原生/iframe 混合插件、React SDK、声明式组件目录、弹层、CSS 隔离以及插件停用/卸载均有回归。Mod 包继续被拒绝。

## 截图与复现

保存并检查了 **12 张实际界面截图**：四个插件各一张桌面、一张移动端，另有 Drive 冲突确认、Drive 编辑器工具栏、提示词编辑器工具栏、对话输入框上方开关。

截图目录：`/workspace/openfic-verification/declarative-migration/screenshots/`。

- [项目统计桌面](/workspace/openfic-verification/declarative-migration/screenshots/project-statistics-desktop.png) / [移动端](/workspace/openfic-verification/declarative-migration/screenshots/project-statistics-mobile.png)
- [Drive 桌面](/workspace/openfic-verification/declarative-migration/screenshots/google-drive-sync-desktop.png) / [移动端](/workspace/openfic-verification/declarative-migration/screenshots/google-drive-sync-mobile.png)
- [Handoff 桌面](/workspace/openfic-verification/declarative-migration/screenshots/handoff-workflow-desktop.png) / [移动端](/workspace/openfic-verification/declarative-migration/screenshots/handoff-workflow-mobile.png)
- [提示词桌面](/workspace/openfic-verification/declarative-migration/screenshots/prompt-elements-desktop.png) / [移动端](/workspace/openfic-verification/declarative-migration/screenshots/prompt-elements-mobile.png)
- [对话输入框上方开关](/workspace/openfic-verification/declarative-migration/screenshots/prompt-above-composer.png) / [编辑器操作](/workspace/openfic-verification/declarative-migration/screenshots/prompt-editor-toolbar.png)

先构建前端，使用独立数据目录启动 `tests.plugins.e2e_app:app`，等待 health 就绪，以 `frontend/e2e/serve-plugin-preview.mjs` 提供 dist，再设置 `OPENFIC_E2E_BACKEND/BASE_URL/CHROMIUM_PATH` 运行：

```sh
cd backend
.venv/bin/pytest tests/plugins -q
cd ../frontend
npm run type-check
./node_modules/.bin/tsc -b
npm run lint
npm run build
./node_modules/.bin/playwright test e2e/declarative-effects.spec.ts e2e/declarative-css.spec.ts e2e/native-examples.spec.ts e2e/plugins.spec.ts e2e/plugin-sdk.spec.ts e2e/declarative-showcase.spec.ts e2e/declarative-plugins.spec.ts e2e/app-shell-regression.spec.ts
```

全部 24 项使用同一最终生产构建运行通过；OAuth 完整链路在后端刷新事件补齐后又专项运行通过。机器可读结果、包和截图 SHA-256 见 [plugin-native-examples-results.json](./plugin-native-examples-results.json)。原始最终日志为证据目录下的 `delivery.log/xml`、`oauth-browser.log/xml`、`backend-final.log`；早期调试失败不计入最终通过结果。

验证范围为 Chromium 桌面及移动视口，没有启动原生 Tauri 窗口或 Safari/Firefox；移动端按目标视口重新加载，不覆盖桌面到手机宽度的宿主切换动画。Drive、OAuth 和模型服务使用仓库协议替身，没有连接真实 Google 账号或外部模型。后端全量未重跑，本轮仅报告插件专项结果。
