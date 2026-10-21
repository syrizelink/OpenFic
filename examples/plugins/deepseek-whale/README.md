# DeepSeek 小鲸鱼：原生插件 SDK 验证移植

本示例参考 [MeteorNOX/DeepSeek-Balance-Whale-Widget](https://github.com/MeteorNOX/DeepSeek-Balance-Whale-Widget)，以 OpenFic 公共 SDK 重写交互与记账逻辑。参考版本为 0.4.2，提交 `5247dd6813d6e4430728f39ccc63d43cda046022`。这是用于验证 SDK 的核心功能移植，不是原插件的完整复刻。

源码只调用插件公开接口及 Python 标准库，不导入应用内部业务模块。宿主没有 DSH 路由、DOM 注入、账户/插件协议兼容层，也没有小鲸鱼专用 API。UI 使用原生声明式组件与 PostCSS 作用域样式，没有 iframe、HTML 或插件浏览器 JS。

## 安装与使用

1. 使用包含本轮 SDK 的 OpenFic。在「插件管理」确认可信来源，上传 [deepseek-whale-1.1.0.zip](../dist/deepseek-whale-1.1.0.zip)。安装后默认停用。
2. 在插件配置填写自己的 DeepSeek API Key，按需设置低余额阈值、每日预算（0 关闭）。密钥加密保存，只发送至 `https://api.deepseek.com/user/balance`，不会读回到 UI。不读取宿主已有模型提供商的密钥。
3. 启用后出现全局挂件。点击刷新按钮获取余额，之后每 60 秒刷新；没有配置密钥时不联网。拖动顶部手柄或用方向键移动，位置持久化；点击角色切换台词。
4. 设置按钮或侧栏「DeepSeek 小鲸鱼」打开独立原生页面，可修改大小、台词、显示状态及今日观测消费。隐藏后从设置页重新显示。停用会移除整个挂件。
5. 原生 Agent 完成回合后，气泡显示该回合的 USD 费用估算；独立页面显示今日用量与最近记录。不需创建额外工具或启用特定 Graph。

## 覆盖与取舍

| 原插件能力 | 本次实现 |
| --- | --- |
| 桌宠悬浮、拖动、大小、位置记忆、点击台词 | 原生 `app.overlay` + `FloatingPanel` + `Image`，鼠标/触摸/键盘均可用 |
| DeepSeek 余额与自动刷新 | 固定官方 API，区分赠金、充值金与总余额；请求失败保留旧值并标记过期 |
| 今日消费、充值、预算、低余额提示、手动校正 | 按账户/币种/北京时间日期分组的余额观测账本，分开记录下降与增加 |
| 回合费用、模型用量反馈 | 内置 Agent 已提交的主/子 Agent USD 增量及成功回合通知；事件去重、按 revision 聚合 |
| 设置/历史/显示隐藏/自定义台词 | 原生组件独立页面，支持移动视口 |
| DSH 账户登录、DSH 提供商/自定义网关、DSH 内部事件 | 不移植，沿用 OpenFic 的独立密钥配置与公开用量事件 |
| 完整气泡模块编辑器、角色上传、音效、GIF 状态、像素透明区点击穿透 | 不移植，本次以一张原始素材与文字气泡验证资源和交互链 |
| 更新安装器、本地 Codex 扫描、复杂峰谷价格/补账自动化 | 不移植；安装与更新沿用 OpenFic 插件管理 |

余额下降可能来自 API 调用、赠金过期等原因，充值/赠金增加也可能掩盖同一观测间隔中的消费。因此本插件明确显示「观测消费」，不能代替完整账单，也不补算安装前或停用期间数据。校正先刷新余额，成功后保存差额，后续新观测继续累计。账户或币种变化建立新基线，旧账户的余额不会显示为新账户余额。

OpenFic 模型费用取自宿主配置的 USD 价格，可能来自任意服务商，与 DeepSeek 的 CNY/USD 余额观测分开显示，不做汇率换算。缓存输入已经包含在 input 中，总 token 不重复相加。中断回合的费用保留在每日统计，但不混入后续成功回合；某些子 Agent 事件没有模型名称，显示「未提供模型名称」。后台子 Agent 在父回合完成后才提交的增量仍进入每日明细，但不会回写已经显示的上一轮气泡。通知是尽力送达，未启用时不回放历史。

账本保留最近 365 天，模型明细最多 3000 条、去重 ID 最多 5000 条、未完成回合最多 100 个。高频使用可能使当前日明细达到上限；示例没有完整账单归档或跨设备同步能力。配置/数据属于当前后端实例。

## 通用 SDK 发现

此次移植补充 `app.overlay/ui.overlay`、包内只读 `assets.read` 和 `Image`、可复用 `FloatingPanel`、`usage.recorded/turn.settled` 观察事件。并提供公开 `context.invalidate_ui()`，避免自定义命名空间事件被误用作宿主通知。同时修复仅修改 secret 设置时原生 UI 不刷新的问题，以及 Slider 标签未命名实际滑块的问题。独立的 `plugin-overlay-probe` 测试插件复用相同接口，验证浮层不是按小鲸鱼 ID 特判。

接口、权限、边界见 [声明式 UI](../../../docs/develop/declarative-plugin-ui.md) 与 [SDK](../../../docs/develop/plugin-sdk-v2.md)，验证结果见 [验证记录](../../../docs/develop/plugin-whale-verification.md)。

## 素材与打包

`assets/whale.png` 是上游 `assets/DSniang1.png` 的逐字节副本，仅改文件名。原图不属于 MIT 代码许可：上游声明按原样随插件分发、仅用于运行本插件、不授予再许可。保留 [上游代码许可](./UPSTREAM-LICENSE) 和 [上游完整素材来源说明](./UPSTREAM-PROVENANCE.md)，此处不扩大授权范围。未复制上游 DSH JavaScript 运行代码、其他图片或音频。

```bash
python examples/plugins/build_package.py examples/plugins/deepseek-whale examples/plugins/dist/deepseek-whale-1.1.0.zip
```
