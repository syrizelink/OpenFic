# 编辑器插件工具栏与 Lucide SDK 验证

验证日期：2026-10-20；分支 `feat/extension-host`，基于 `24331c5`。机器可读记录见 [plugin-editor-toolbar-results.json](./plugin-editor-toolbar-results.json)。

## 最终行为

章节和笔记编辑器的插件入口放入现有工具栏，使用与内置操作相同的图标按钮和 Tooltip。内容通过 Radix Popover/Dialog 的 Portal 展示，不在正文上方插入面板；多个入口横向滚动，不换行或增加工具栏高度。旧 `editor.context`、`editor.panel` 包继续安装，分别默认打开浮层、对话框。iframe 的 `ui.resize()` 只调整浮层内部高度，内容受到视口约束。

SDK 增加清单 `icon`、`presentation: "popover" | "dialog"`，并补充编辑器上下文的 `kind`。声明式 UI 增加 `Icon`（别名 `LucideIcon` / `Project.Icon`），可使用当前宿主全部 **1748 个 Lucide 图标**。名称、属性、能力约束由同一目录验证和生成类型；图标代码通过一个共享模块延迟加载，并加入构建预缓存。详见 [声明式 UI 协议](./declarative-plugin-ui.md#编辑器工具栏与图标)。

Google Drive 与提示词示例升级至 **1.2.0**，使用 `CloudUpload`、`TextCursorInput` 工具栏按钮及浮层；Drive 浮层内部的操作按钮也使用声明式 Icon。提示词在笔记入口隐藏不支持的撤销操作。可从管理页更新安装包，保留已有插件存储和配置：

- [Google Drive 1.2.0](../../examples/plugins/dist/google-drive-sync-1.2.0.zip)
- [提示词元素 1.2.0](../../examples/plugins/dist/prompt-elements-1.2.0.zip)

项目统计和 Handoff 的 1.1.0 安装包保持可用，本轮同样执行安装和 UI 回归。

## 验证结果

| 检查 | 结果 |
| --- | --- |
| 后端插件回归 `pytest tests/plugins -q` | **82 passed** |
| 最终生产构建插件、CSS、SDK 与导航回归 | **25 passed**：14 个真实浏览器用例、11 个纯逻辑用例 |
| 原有章节/笔记编辑回归 | **3 passed**：插件未安装、停用、启用三种状态 |
| 前端合计 | **28 passed，0 failed，0 skipped，0 flaky**；其中 17 个浏览器用例 |
| 静态检查 | 目录与 SDK 类型新鲜度、类型感知 Oxlint、`tsc -b`、Oxlint、改动文件 Oxfmt、Ruff 检查/格式均通过 |
| 生产构建 | 通过；Lucide 延迟模块包含在预缓存中 |
| 示例交付包 | 四个 ZIP 均与对应源码逐字节一致，两个 SDK 类型分发副本一致 |
| wheel 内嵌前端 | **745 个文件**与最终验证构建逐字节一致；新增后端验证代码、SDK 类型和组件目录一致 |

新增 [工具栏端到端用例](../../frontend/e2e/editor-plugin-toolbar.spec.ts) 使用实际 ZIP 安装 API 和真实章节/笔记，验证：

1. 安装 13 个入口前后，工具栏和编辑器正文容器的坐标与尺寸完全相同；入口横向溢出，无正文内联容器。
2. 工具栏与声明式树均渲染 Lucide SVG；标准名称转换、描边、无障碍名称可用，省略图标的旧包正常回退。
3. 键盘打开、Escape 关闭及焦点恢复，浮层输入、原编辑器光标位置插入与数据库保存。
4. 旧 `editor.context` iframe 在浮层打开，调用真正的 `OpenFic.ui.resize(180)` 后高度为 180px，编辑器容器尺寸不变。
5. 旧 `editor.panel` 在对话框打开，编辑器容器尺寸不变。
6. 章节切换到笔记后，插件上下文更新为当前笔记。
7. 390px 移动视口及模拟软键盘下，触摸事件不抢走输入焦点，浮层边缘不超出视口；停用后入口消失。

完整回归还覆盖四个示例的桌面/移动 UI、Drive OAuth/冲突/Agent 同步工具、Handoff 模型交接及原生 Graph 切换、提示词注入/编辑器操作、React iframe SDK、权限拒绝、项目选择器、作用域 CSS、管理与卸载。原有编辑回归覆盖手工编辑、自动保存、撤销重做、快捷键保存、章节切换、笔记保存、刷新恢复及权限边界。

## 证据与复现

本地证据目录：`/workspace/openfic-verification/editor-plugin-toolbar/`。最终日志使用 `browser-final.log`、`writing-final.log` 和对应 `*-final-results.json`，此前调试及中间复测不计入最终结果。

- [Drive 工具栏浮层截图](/workspace/openfic-verification/editor-plugin-toolbar/browser-final-artifacts/plugin-sdk-SDK-examples-Dr-975bf-prompt-injection-and-editor-chromium/drive-editor-toolbar.png)
- [提示词工具栏浮层截图](/workspace/openfic-verification/editor-plugin-toolbar/browser-final-artifacts/plugin-sdk-SDK-examples-Dr-975bf-prompt-injection-and-editor-chromium/prompt-editor-toolbar.png)
- [移动端浮层截图](/workspace/openfic-verification/editor-plugin-toolbar/browser-final-artifacts/editor-plugin-toolbar-edit-2ddc8--selections-notes-and-touch-chromium/toolbar-mobile.png)

使用专用临时数据后端 `tests.plugins.e2e_app:app`。生产构建由 `e2e/serve-plugin-preview.mjs` 提供运行时后端地址；原有编辑回归因包含开发模块权限桥检查，在 Vite 开发服务执行。前端最终检查为 `npm run type-check`、`tsc -b`、`npm run lint`、改动文件 `oxfmt --check` 和 `npm run build`。

```bash
# frontend，需先配置 OPENFIC_E2E_BASE_URL / OPENFIC_E2E_BACKEND 等环境变量
node_modules/.bin/playwright test e2e/editor-plugin-toolbar.spec.ts e2e/declarative-effects.spec.ts e2e/declarative-css.spec.ts e2e/native-examples.spec.ts e2e/plugins.spec.ts e2e/plugin-sdk.spec.ts e2e/declarative-showcase.spec.ts e2e/declarative-plugins.spec.ts e2e/app-shell-regression.spec.ts
# 原有编辑回归改用 Vite 服务地址
node_modules/.bin/playwright test e2e/writing-regression.spec.ts
```

浏览器为无头 Chromium；移动端用例模拟 pointer 事件和 visualViewport 键盘尺寸，未执行物理移动设备或原生桌面壳实机测试。Google 和模型业务使用专用测试应用的协议仿真服务，没有授权真实 Google 账户。本轮验证不等于重新运行整个后端测试集。
