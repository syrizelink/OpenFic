# 统一插件结构迁移验证

本轮将插件入口、资源与开发工具改为按清单定位，并迁移七个已有示例、浏览器测试插件及安装包。使用方式见 [插件结构](./plugins.md#包格式)，开发命令见 [Devtools](./plugin-devtools.md)。

## 验证结果

| 检查 | 结果 |
| --- | --- |
| 全量后端回归 | 2,370 passed，19 skipped；220.31 秒 |
| 最终共用打包器、插件和 CLI 复验 | 141 passed，1 skipped；33.38 秒，包含 18 项布局与兼容用例 |
| Playwright | 33 项独立用例通过：22 项浏览器端到端、11 项 CSS/effect 逻辑检查 |
| 前端格式、类型感知 lint、tsc、生成物检查与生产构建 | 通过 |
| Python lint 与新增模块格式 | 通过 |
| 七个当前示例与 ZIP | 已递增版本并全部迁移；包内容逐文件与源码一致，无 backend/frontend 目录 |
| 示例检查 | 七个示例静态检查、全部 Python lint 通过；devtools-demo 实际执行严格 Ruff/Oxlint/TypeScript 检查 |
| SDK npm 包和正式 wheel | 打包成功；SDK 分发内容、新增宿主模块及全部内嵌前端文件与源码/构建逐字节一致 |

19 项跳过来自当前平台及可选集成环境，没有计作通过；最终专项中的 1 项为平台条件跳过。生产构建保留已有的大 chunk 提示。主应用前端资源数、原始大小及全部 JS 的 gzip 汇总均与改造前相同。

浏览器回归发现仓库打包脚本会间接导入模型库；已抽取共用的纯标准库 package_builder 模块，并用 Python -S 验证独立脚本与宿主生成相同 ZIP，不要求安装整套应用依赖。

## 实现范围

- 新清单统一使用 `entry` 和 `resources`；不要求代码或页面位于 backend/frontend。最小插件只有 plugin.json 与 main.py。
- Python 入口按独立包加载，支持相对导入；更新、停用和激活失败时清理其子模块，避免同名模块污染与旧实现残留。
- 静态 HTTP、票据资源与 SDK assets.read 共用声明式公共资源边界，代码入口与清单不能被公开根覆盖。包含跨平台大小写保护和路径/符号链接检查。
- iframe 入口在应用脚本之前自动加载 SDK；原始文件不被改写，CSP、opaque origin、票据作用域及认证规则保持原有约束。旧页面手写 SDK 脚本仍可运行。
- 构建监听优先使用插件根 package.json，可通过 --script-dir 指定任意工具目录；旧 --frontend-script 是 --watch-script 的命令别名。
- 开发检查读取完整源码；运行包通过 plugin.dev.json 的 package.include/exclude 选择文件。被排除的开发文件仍接受语法/lint，但不消耗运行包的文件/大小预算。静态 UI 检查针对运行模块，fixture 继续来自开发源码。
- 所有当前示例使用 main.py，图片放在 assets，自带界面按需放在 panel；开发示例通过 main.py/views.py/actions.py 演示相对导入。旧原生包保留读取、重启、导出和升级能力。

## 验证覆盖

后端专项检查任意目录与嵌套入口、模块隔离及更新清理、源码与运行包分离、未打入包的页面脚本、HTML 注释/脚本字符串中的假 head 标记、SDK 插入顺序、公共图片、私有文件、路径穿越、重复字段、重校验旧清单、构建目录选择和旧包升级后的存储保留。

新增浏览器用例从真实旧包开始，保留 frontend 下的页面及手写 ../../sdk.js：安装、增加计数、显示包内 GIF；再升级为根 main.py 和包含空格的 panels/custom view 目录，确认图片可读、计数保留、SDK 仅由宿主加载且私有文件返回 404。

原有浏览器回归覆盖全部业务示例、项目统计更新/导出/卸载、React 自带 UI、Radix/项目选择器、CSS 隔离、章节/笔记工具栏、移动布局、Google Drive/Agent 工具、Handoff Graph、提示词注入与小鲸鱼。开发服务另验证 views.py 的热重载、相对导入更新、配置和计数保留、非法 Props 预检失败、入口激活失败回退、iframe 资源重载及 Inspector；编辑器按插件未安装、停用、启用三种状态验证编辑保存和权限边界。

## 复现

```bash
cd backend
uv run pytest -q
uv run pytest tests/plugins/test_layout.py tests/plugins/test_devtools.py -q
uv run python -m app.cli plugin check ../examples/plugins/devtools-demo --run-checks --strict
cd ../frontend
pnpm type-check
pnpm exec tsc -b
pnpm build
```

浏览器使用独立数据的 tests.plugins.whale_e2e_app:app 和生产构建；设置 OPENFIC_E2E_BACKEND、OPENFIC_E2E_BASE_URL、OPENFIC_E2E_CHROMIUM_PATH。开发工具测试使用真实 openfic plugin dev 服务及一次性源码副本，并设置 OPENFIC_E2E_PLUGIN_SOURCE；不会编辑仓库示例。writing-regression 使用 Vite 导入权限网关。浏览器运行期间不重建静态资源。

机器可读结果及最终计数见 [plugin-layout-results.json](./plugin-layout-results.json)。原始日志和截图位于执行环境的 `/workspace/openfic-verification/plugin-layout/`。

## 边界

使用 Linux/Chromium，没有运行原生桌面安装器或 PostgreSQL 集成环境。外部 Google Drive、DeepSeek 和模型调用使用测试协议仿真；未连接真实云账号或付费模型。

Python 插件仍按可信代码运行；本轮没有增加执行沙箱。打包器不安装依赖或编译任意源码。静态检查无法证明动态导入、任意文件读取或业务分支的完整性，作者需显式包含这些运行文件并做运行测试。旧格式继续可读，新作者应使用 entry/resources 及根相对资源路径。
