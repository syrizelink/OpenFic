# 插件 Devtools

Devtools 包含离线检查与打包 CLI、独立数据的源码开发服务、插槽预览和宿主 Inspector。源码结构和运行包规则见 [统一插件结构](./plugins.md#包格式)。组件校验复用实际安装器和声明式组件目录；样式诊断复用宿主的 PostCSS 编译器。普通服务默认不采集诊断。

## 检查和打包

```bash
# 已安装 OpenFic 时直接使用 openfic；仓库开发也可在 backend 中运行 uv run python -m app.cli
openfic plugin check ./my-plugin
openfic plugin check ./my-plugin --run-checks --strict --json
openfic plugin check ./my-plugin.zip --json
openfic plugin pack ./my-plugin --output ./my-plugin.zip --run-checks --strict
```

默认检查不导入或执行插件 Python，不加载应用设置、不创建数据库或加密密钥，不安装依赖。它会启动 Devtools 自带的 Node CSS 检查器；`--run-checks` 才会执行插件项目自己的脚本及 Ruff，因此应只对可信源码使用。

| 检查 | 覆盖与边界 |
| --- | --- |
| 安装包 | 根清单、API/版本/插槽/能力、统一 entry 和 resources、运行文件选择、大小、路径、重复文件与符号链接；与安装器使用同一提取器 |
| Python | 内建 AST 语法检查；`--run-checks` 执行已安装的 Ruff |
| 声明式 UI | 可静态识别的组件、Props 和字面值、组件权限、Image 资源、静态 command 注册及 action 分支；不会求值动态表达式 |
| 声明式 CSS | 运行模块顶层 `CSS/STYLES` 字面量与 fixture 的 CSS，通过与宿主相同的编译器报告被过滤/无效样式 |
| 网络与前端资源 | 可识别的字面量 HTTP 域名和 network 声明；HTML 相对 script/link/img/source 引用及公共资源边界；同时检查源码与实际运行包；不抓取外部资源 |
| JS/TS/框架源码 | 识别源码内各 package.json 的 lint、type-check/typecheck 脚本；`--run-checks` 在原项目目录执行，不替换项目配置 |

没有配置、没有依赖或没有执行的检查会明确显示为 warning、failed 或 not-run。`--strict` 将警告和未执行检查都视为失败，适合配合 `--run-checks` 用于 CI 和打包。ZIP 检查不能替代原项目源码的 lint；不要把编译后的 JS 通过包格式校验理解为源码质量检查通过。工具不会自动安装 npm/pip 依赖。

Python AST 只检查可靠识别的字面量结构。动态 UI、通过辅助函数产生的 action、动态网络地址及业务分支无法仅靠静态检查证明；JSON 输出包含 staticNodes、dynamicValues、actionIdsChecked/actionIdsUnverified、documents 等覆盖信息。未在静态分支中找到的 action ID 是诊断警告，运行行为仍须通过预览或测试验证。

可以在插件根添加 `plugin.dev.json`：

```json
{
  "fixtures": [
    {"view": "overview", "file": "ui/overview.json"}
  ]
}
```

fixture 是实际 render 文档，使用真实校验器验证，包括复合组件父子结构、权限及文档预算。也可通过 `--ui ./document.json` 添加文档。动态渲染的不同状态应提供多个 fixture；fixture 本身不证明运行函数在相应上下文中一定返回相同结果。

## JS/TS 与精确组件类型

插件应自行声明前端依赖、Oxlint/ESLint、TypeScript 和构建配置。工具只执行已配置脚本，不会将宿主源码 lint 配置强行套到独立插件。声明式 UI 类型由同一组件目录生成：

```ts
import type { UINode, UIPropsFor } from '@openfic/plugin-sdk';

const image: UIPropsFor<'Image'> = { asset: 'assets/logo.png', alt: 'Logo' };
const valid: UINode = { type: 'Button', props: { size: '2', onPress: 'save' } };
// 类型错误：asset 属于 Image，不能用于 Button。
const invalid: UINode = { type: 'Button', props: { asset: 'logo.png' } };
```

`UINode` 是以组件名称区分的联合类型，别名遵循宿主的项目组件优先规则。通用 `UIProps` 仍保留，供反射/通用工具使用；需要按组件约束时使用 `UINode`、`UIPropsFor<C>` 或 `UIComponentPropsMap`。事件仍是 opaque action ID，TypeScript 不会证明该 ID 有后端实现。

安装 `@openfic/plugin-devtools` 后还提供 `openfic-plugin-ui css file.css --json`，检查单个声明式样式表，也可输入包含 css 字段的 JSON 文档。该包与宿主共享编译器，不需要 React。仓库开发使用本地包，当前任务未发布到 npm；可从 `packages/plugin-devtools` 执行 npm pack，或使用 file: 依赖安装。

## 独立开发服务与热重载

```bash
openfic plugin dev ./my-plugin --port 8011
# 前端单独使用 Vite 时，VITE_BACKEND_URL 应指向这个后端：
openfic plugin dev ./my-plugin --port 8011 --frontend-url http://127.0.0.1:9000
# 执行插件根 package.json 中已有的构建监听脚本
openfic plugin dev ./my-plugin --watch-script build:watch
# 工具项目位于自选子目录时显式选择
openfic plugin dev ./my-plugin --watch-script build:watch --script-dir tools/ui
```

打开 CLI 输出的 `/extensions/devtools`。默认数据保存在源码的 `.openfic-dev/`，包括开发数据库、插件配置和插件存储；它被打包器和监听器排除，仓库也已忽略。可以通过 `--data-dir /other/empty-directory` 指定目录。目录必须为空或包含绑定本源码的开发标记，不能直接使用已有应用数据；源码内的自定义数据目录必须位于 `.openfic-dev/` 下。

开发服务固定绑定 127.0.0.1，在导入应用前设定独立数据目录，覆盖当前环境的 OPENFIC_DATA_DIR。它保留显式配置的应用密码。独立开发数据不等于 Python 执行沙箱；插件仍按现有可信代码模型运行。

默认从根 package.json 执行脚本；根不存在时查找唯一匹配的脚本项目，多个候选需指定 --script-dir。--frontend-script 作为旧命令别名保留。

监听 Python、清单、静态资源和构建产物；node_modules、缓存、Git、ZIP 及开发数据目录不参与快照。检查基于完整源码，安装按 plugin.dev.json 的 package.include/exclude 选择运行文件。编辑后先做离线预检，再通过原安装器替换，保留配置和存储。只有显式开发会话的目标插件允许同版本替换，普通安装/更新仍要求递增版本。预检失败或激活失败保留旧版本；错误出现在开发页，修复后自动重试。修改 plugin ID 需重启开发会话。后端 interval/dispose 沿用现有停用、激活与清理流程。

默认热重载不反复执行 lint/type-check；开发页展开“源码检查覆盖范围”可查看哪些检查未运行。可在另一个终端运行自己的 lint/type-check/watch，或在打包前执行严格检查。前端源代码需要先经作者的构建流程产出清单 entry；热重载不会在运行时编译任意 React/Vue 源码。

## 预览与 Inspector

预览支持实际视图与插槽、960/768/390px 视口、浅/深主题、语言和 JSON 上下文。为了让 fixed 定位、媒体查询和 Portal 使用正确的视口，开发预览使用**同源宿主 iframe** 承载一份真实渲染器；这不改变生产声明式 UI 的原生渲染方式，也不让插件获得主页面 DOM。iframe 插件仍在其原有的无同源 sandbox 中运行。

工具栏插槽通过按钮打开 Popover/Dialog，不直接占用编辑器正文；全局浮层在预览视口内定位。预览不伪造编辑器：没有真实编辑器时，editor SDK 调用会显示权限或上下文错误。项目/章节 ID 等上下文需要开发数据库中的实际数据，填写 JSON 不会自动创建实体。

Inspector 可查看：

- 服务端校验后的组件树、Props 和实际上下文；原始 CSS、宿主编译后 CSS 与过滤提示。
- render/action、宿主 UI effect、iframe RPC、公共 SDK 调用、Agent hook 和提交后事件的结果/错误/耗时。
- Python 直接使用的 storage/secrets/files/assets/http/models、业务 API 网关调用；未通过这些公开入口的任意 Python 调用不被自动追踪。
- iframe 的 error/unhandledrejection。传统跨源脚本可能仅提供 Script error；使用 module 或 crossorigin="anonymous" 并由服务端正确提供 CORS 响应，浏览器才会公开详细错误。示例演示该标准用法。

采集默认关闭。`plugin dev` 自动开启；要调试普通实例中的已安装插件，显式运行 `openfic serve --plugin-devtools`，再从插件管理进入开发工具。停用采集需关闭该进程并以普通方式启动，普通插件不能通过 SDK 网关开启 Inspector 或读取它。

前端诊断也统一经过认证接口发送到服务端，使用实际插件设置和已读取的 secret 值做脱敏后保留；前端不建立原始历史或 localStorage 日志，预览与 Inspector 之间不使用跨窗口消息转发诊断；iframe 插件的异常通过已有的 SDK 校验通道上报。敏感字段、Bearer、声明为 secret 的配置值及 secret 存储调用会被隐藏，错误位置中的视图 ticket 会被移除。每个后端仅保留最近 200 条记录，单条载荷限制为约 64 KiB，深度/列表/字符串也有限制；超限会显示截断。前端采集最多并发 8 个报告，拥塞时可能丢弃诊断，不能作为审计系统。清空或退出服务会丢弃历史。

Inspector 的记录可能包含正文、提示词和业务响应等开发内容。脱敏只覆盖上述已知范围；导出前应检查自定义插件返回的其他敏感业务内容。界面支持按 SDK/前端/hook/观察事件/错误筛选，清空和导出脱敏 JSON。

## 示例和验证

[devtools-demo](../../examples/plugins/devtools-demo/README.md) 提供原生页面、工具栏、浮层和自带 JS 的 iframe，包含可执行的前端 lint/type-check 配置、UI fixture、权限错误、CSS 过滤与 secret 脱敏场景。它不包含任何业务插件专用适配。

Devtools 初始验证见 [Devtools 验证报告](./plugin-devtools-verification.md)；当前统一目录、运行包选择与旧包迁移的验证见 [统一插件结构验证](./plugin-layout-verification.md)。
