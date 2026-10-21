# 小鲸鱼原生移植与 SDK 验证

本页保留历史验证结果。旧版安装包已迁移，当前下载见 [示例插件](./plugin-examples.md)，目录迁移与最新验证见 [统一插件结构验证](./plugin-layout-verification.md)。

验证日期：2026-10-20；分支 `feat/extension-host`，基于 `cc15585`。机器可读记录见 [plugin-whale-results.json](./plugin-whale-results.json)。

## 移植范围

参考上游 0.4.2，提交 `5247dd6813d6e4430728f39ccc63d43cda046022`。交付 `deepseek-whale-1.0.0.zip`，从插件管理安装并启用即可运行；完整安装说明、功能对照、记账限制和素材许可见 [插件 README](../../examples/plugins/deepseek-whale/README.md)。

本次是核心交互的原生 SDK 移植。宿主没有 DSH 模块加载器、路由/账户协议、DOM 注入或按插件 ID 判断的适配。余额 HTTP、账本、预算提示、台词与 Agent 用量聚合都在插件内；宿主仅新增下表的通用接口。

| SDK 发现 | 最终实现 |
| --- | --- |
| 现有插槽无法表达不占页面布局的常驻挂件 | `app.overlay` + 独立 `ui.overlay` 能力，仅接受声明式视图，空白区域不截获鼠标 |
| 声明式 UI 无法读取/显示本插件图片 | 公开只读 `assets.read` + `Image`，包路径约束、传输上限、raster MIME 白名单 |
| 拖动交互不宜逐像素往返后端 | 通用 `FloatingPanel`，浏览器本地移动，结束后提交 `{x,y}`；触摸/方向键、窗口尺寸约束 |
| 较早的 Agent hook 不能证明费用已落库 | `usage.recorded/turn.settled`，独立观察者载荷/session、超时与错误隔离，按 revision 关联 |
| 仅改 secret 配置不会刷新原生视图 | 配置成功后发送 `ui.invalidate` |
| 自定义事件有插件命名空间，不能充当宿主刷新通知 | 公开 `context.invalidate_ui()` / `context.call("ui.invalidate")`，要求 `ui` |
| Radix Themes 把 Slider 标签放在根元素 | 同时为实际聚焦的滑块设置无障碍名称 |

独立 `plugin-overlay-probe` 使用相同 FloatingPanel、Image、输入与存储接口，验证无专用适配。声明式目录现有 **122 个 Radix Themes 入口、13 个项目组件**；新增接口没有引入前端依赖。

## 自动化验证

| 检查 | 最终结果 |
| --- | --- |
| 完整后端插件 + Agent runtime | **1066 passed，8 skipped**；补齐子 Agent 元数据后的定向复测 **22 passed** |
| 小鲸鱼完整安装与浏览器验证 | **2 passed**，桌面/触摸/两个原生浮层及连续 Agent 回合 |
| 原有生产插件/组件回归 | **25 passed** |
| 原有章节/笔记编辑回归 | **3 passed** |
| 前端合计 | **30 passed，0 failed，0 skipped，0 flaky**；19 个浏览器用例，11 个纯逻辑用例 |
| 静态检查 | 目录与 SDK 类型新鲜度、类型感知 Oxlint、`tsc -b`、小鲸鱼 spec 独立类型检查、Oxlint、改动前端文件 Oxfmt、后端 Ruff 均通过；新增 Python 文件格式检查通过 |
| 构建与交付 | 生产构建、ZIP/源码/原图一致性、SDK 类型副本一致性及 wheel 内嵌文件核对均通过 |

后端覆盖：插件安装与能力拒绝、资源路径穿越/符号链接/大小限制、真实素材字节、余额下降/充值/校正/账户和币种切换、请求失败保留旧值、secret 不回传、通知去重、观察者异常隔离、载荷不可互相污染、缓存 token 不重复计算，以及中断 revision 不混入后续成功回合。原有 Agent 回归覆盖执行器、持久化、审批/恢复、取消、子 Agent、上下文与压缩等。压缩计费测试还在观察回调中用独立 session 查询已提交的 Task 费用，确认提交顺序；缺少实际模型身份时不误标为主模型。

小鲸鱼浏览器用例通过真实管理界面上传 ZIP，验证：

1. 原生图片尺寸与无 iframe；启用前后编辑器容器尺寸完全一致，挂件存在时正文编辑、快捷键保存及数据库更新可用。
2. 余额 100 → 90 → 120，消费与充值分开累计；503 失败显示过期值；设置页校正到 17.50。
3. 点击台词、修改台词与大小、鼠标拖动、刷新后位置恢复、方向键移动，以及设置页/挂件跨视图刷新和显示隐藏。
4. 只修改 secret 时旧账户余额隐藏，密钥不进入 DOM；390px 视口边缘约束、真实 Chromium CDP touch 事件拖动。
5. 同时安装独立浮层探针、输入文本安全渲染、SVG 图片被拒绝；停用小鲸鱼不移除另一插件。
6. 使用真实内置 Agent 执行器连续发送两轮消息，数据库提交费用与插件每轮增量精确对照，按 revision 区分；USD 费用显示八位小数。

完整浏览器回归还覆盖原有工具栏/Portal/图标、四个示例、Drive OAuth/冲突/Agent 同步工具、Handoff Graph、提示词注入、React iframe、插件管理、项目选择器、PostCSS 隔离及导航。单独的原有章节/笔记回归覆盖未安装、停用、启用三种状态下的手工编辑、自动保存、撤销重做、快捷键保存、切换、刷新恢复及 SDK 权限边界。

## 资源与包

相比前一轮工具栏版本的生产构建，文件数仍为 **745**，全部前端文件原始大小增加 **4894 bytes**，所有 JS 逐文件 gzip level 6 的总量增加 **1646 bytes**（约 1.6 KiB）。这些是两次相同环境构建的整体差值，不是网络传输或加载耗时基准。角色图片仅在插件 ZIP 中，不内嵌进主程序。

ZIP 与全部源码逐字节核对；图片与上游 `assets/DSniang1.png` 相同，SHA256 为 `dcc456613dbb1102a4b7ef636a8b622371e33b763489d6249c434fb54248ba5c`。保留上游代码许可与素材来源说明，未把图片声明成 MIT 素材。

隔离目录构建 wheel，核对内嵌前端 745 个文件与被测生产构建逐字节一致，并核对新增后端接口、执行器、SDK JS/类型/组件目录。此检查不等于运行桌面壳或签名安装器。

## 证据与复现

本地证据目录 `/workspace/openfic-verification/whale-port/`。最终结果以机器记录中的日志为准；此前调试失败不计为通过。调试发现了滑块标签、错误使用命名空间事件，测试应用路由被 SPA fallback 遮挡，以及对不占布局的浮层容器使用可见性断言的问题，均已修复；测试清理改为不掩盖原始失败。

- [全部验证完成后截取的章节编辑器与小鲸鱼](/workspace/openfic-verification/whale-port/chapter-editor-with-whale.png)
- [移动端触摸拖动后的挂件](/workspace/openfic-verification/whale-port/whale-final-artifacts/deepseek-whale-native-whal-dee3f-le-and-independent-overlays-chromium/whale-mobile.png)
- [真实 Agent 回合费用 UI](/workspace/openfic-verification/whale-port/whale-final-artifacts/deepseek-whale-real-Agent--bcba8-urn-to-the-installed-widget-chromium/whale-agent-usage.png)

```bash
# backend
.venv/bin/pytest tests/plugins tests/agent_runtime -q
OPENFIC_DATA_DIR=/tmp/openfic-whale-e2e OPENFIC_AUTH_PASSWORD='' \
  .venv/bin/uvicorn tests.plugins.whale_e2e_app:app --host 127.0.0.1 --port 8031

# frontend
npm run type-check
node_modules/.bin/tsc -b
npm run lint
npm run build
OPENFIC_E2E_BACKEND=http://127.0.0.1:8031 OPENFIC_E2E_PREVIEW_PORT=9032 \
  node e2e/serve-plugin-preview.mjs
OPENFIC_E2E_BACKEND=http://127.0.0.1:8031 OPENFIC_E2E_BASE_URL=http://127.0.0.1:9032 \
  node_modules/.bin/playwright test e2e/deepseek-whale.spec.ts e2e/editor-plugin-toolbar.spec.ts e2e/declarative-effects.spec.ts e2e/declarative-css.spec.ts e2e/native-examples.spec.ts e2e/plugins.spec.ts e2e/plugin-sdk.spec.ts e2e/declarative-showcase.spec.ts e2e/declarative-plugins.spec.ts e2e/app-shell-regression.spec.ts
# 原有编辑回归需要 Vite 开发服务（包含开发模块权限桥检查），替换 BASE_URL 后执行：
node_modules/.bin/playwright test e2e/writing-regression.spec.ts
```

DeepSeek、Google 与 LLM 的外部响应使用专用测试应用的协议仿真；安装、RPC、数据库、UI 与 Agent 执行链为真实实现。没有使用真实 DeepSeek/Google 账户或产生模型费用。移动端为无头 Chromium 视口和触摸模拟，未执行物理设备或桌面壳实机测试。观察事件是尽力送达，不承诺账单级完整性或停用期间历史回放；完整记账边界见插件 README。
