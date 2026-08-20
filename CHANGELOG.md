# Changelog

## [0.10.1](https://github.com/syrizelink/OpenFic/compare/v0.10.0...v0.10.1) (2026-08-20)


### 🐛 问题修复

* **desktop:** 修复 PyPI 镜像 wheel 文件 403 导致桌面更新失败的问题 ([#315](https://github.com/syrizelink/OpenFic/issues/315)) ([fd99c8b](https://github.com/syrizelink/OpenFic/commit/fd99c8b157be8251c3b3e4a21bfe4899b56c2fbe))
* **desktop:** 限制 setup 错误内容高度 ([#314](https://github.com/syrizelink/OpenFic/issues/314)) ([adaefb9](https://github.com/syrizelink/OpenFic/commit/adaefb9b1b489597929654886807487a64cb7821))
* **openrouter:** 修复 OpenRouter SDK 超时单位混淆导致请求卡住的问题 ([#319](https://github.com/syrizelink/OpenFic/issues/319)) ([422b951](https://github.com/syrizelink/OpenFic/commit/422b951204e25538e6df752573f5e2f3b4fc327a))


### ⚡ 性能优化

* **desktop:** 缩减桌面安装包体积 ([#313](https://github.com/syrizelink/OpenFic/issues/313)) ([0ecbc54](https://github.com/syrizelink/OpenFic/commit/0ecbc5440c7bf24585886f4743dfb037109460ee))


### 📚 文档

* 更新项目文档 ([#320](https://github.com/syrizelink/OpenFic/issues/320)) ([54f18e1](https://github.com/syrizelink/OpenFic/commit/54f18e1b1aa0bad44d178f68cd01fdeab0149e60))


### 🔧 杂项

* **agent:** 允许Agent会话记住输入历史和未发送草稿 ([#316](https://github.com/syrizelink/OpenFic/issues/316)) ([7c0b8f2](https://github.com/syrizelink/OpenFic/commit/7c0b8f27dbb52f895492a24ca1c799e8cd7a9823))
* **branding:** 更新品牌图标与应用标识 ([#321](https://github.com/syrizelink/OpenFic/issues/321)) ([e73b900](https://github.com/syrizelink/OpenFic/commit/e73b900ccb8bd2486a7f1920cacc598cf6bf141a))
* **desktop:** 支持实例删除 ([#324](https://github.com/syrizelink/OpenFic/issues/324)) ([128b057](https://github.com/syrizelink/OpenFic/commit/128b0576b1e94e93bde7ff9a51c9ce727f4751e1))
* **desktop:** 添加桌面端前进后退导航 ([#323](https://github.com/syrizelink/OpenFic/issues/323)) ([70b4af7](https://github.com/syrizelink/OpenFic/commit/70b4af7ced68bf43c086def2ddd37a8a36fda2f2))
* **editor:** 新增成对符号自动补齐设置 ([#317](https://github.com/syrizelink/OpenFic/issues/317)) ([d5322ca](https://github.com/syrizelink/OpenFic/commit/d5322ca5435ead0ff3d6624e55d6af436b05129e))
* **editor:** 新增段落自动缩进设置 ([#311](https://github.com/syrizelink/OpenFic/issues/311)) ([4024a67](https://github.com/syrizelink/OpenFic/commit/4024a67de7afc02048420ab374143c75997928ea))
* **editor:** 新增自动转换半角符号设置 ([#312](https://github.com/syrizelink/OpenFic/issues/312)) ([30fb71e](https://github.com/syrizelink/OpenFic/commit/30fb71e2ee050cc384c1635193db489f35582568))
* **frontend:** 支持提问面板折叠 ([#322](https://github.com/syrizelink/OpenFic/issues/322)) ([1b0b253](https://github.com/syrizelink/OpenFic/commit/1b0b253e0415a2e6847a787a7f3cdcd6b80dff0d))
* **vscode:** 添加 VS Code 开发任务配置 ([#309](https://github.com/syrizelink/OpenFic/issues/309)) ([94503b9](https://github.com/syrizelink/OpenFic/commit/94503b921f42ab8a61b98365889929d4979477b6))

## [0.10.0](https://github.com/syrizelink/OpenFic/compare/v0.9.2...v0.10.0) (2026-08-16)


### ✨ 新功能

* **agent:** 支持主 Agent 自定义标识（颜色与图标） ([#282](https://github.com/syrizelink/OpenFic/issues/282)) ([b802c4d](https://github.com/syrizelink/OpenFic/commit/b802c4d2543938a6fc61fc92c03754d3e9f8ae55))
* **agent:** 支持规则全局与项目作用域 ([#269](https://github.com/syrizelink/OpenFic/issues/269)) ([0fb578a](https://github.com/syrizelink/OpenFic/commit/0fb578aa9c7ace66436f71331029dc82a76b316f))
* **desktop:** 支持数据备份、迁移、还原与自定义数据目录 ([#275](https://github.com/syrizelink/OpenFic/issues/275)) ([23a1fac](https://github.com/syrizelink/OpenFic/commit/23a1fac7e14d9184ebf2e583a8d451ef068cb80a))
* **fonts:** 引入 fontsource 字体支持 ([#294](https://github.com/syrizelink/OpenFic/issues/294)) ([c135ee3](https://github.com/syrizelink/OpenFic/commit/c135ee338975bf3330f179e3eba360ad12727a22))
* **settings:** 支持自定义基础字号与编辑器字号 ([#300](https://github.com/syrizelink/OpenFic/issues/300)) ([ac6da38](https://github.com/syrizelink/OpenFic/commit/ac6da382907886940fb17121d4a2b5bf6742cbcc))
* **telemetry:** 接入 PostHog 远程错误遥测 ([#305](https://github.com/syrizelink/OpenFic/issues/305)) ([08d47ae](https://github.com/syrizelink/OpenFic/commit/08d47aef1bd421993c3b2a952b69a2b468cbd8eb))


### 🐛 问题修复

* **agent:** 修复会话生命周期竞态导致取消和恢复异常的问题 ([#307](https://github.com/syrizelink/OpenFic/issues/307)) ([c1430df](https://github.com/syrizelink/OpenFic/commit/c1430df5a6a6181942f7327206bf51e3c5ba5bc2))
* **agent:** 修复并行工具调用时唯一约束冲突的问题 ([#271](https://github.com/syrizelink/OpenFic/issues/271)) ([5dbe377](https://github.com/syrizelink/OpenFic/commit/5dbe3772a78ac56be85ae19ae23881185c20e4b4))
* **agent:** 工具数量超限不再中断会话并返回错误结果 ([#293](https://github.com/syrizelink/OpenFic/issues/293)) ([b35a744](https://github.com/syrizelink/OpenFic/commit/b35a744e702e30a02b488f9948c433602ae3ff2a))
* **backend:** 修复 LLM 长响应被超时中断的问题 ([#277](https://github.com/syrizelink/OpenFic/issues/277)) ([3259325](https://github.com/syrizelink/OpenFic/commit/32593253ba58143731dba5eb8f359b82234353c1))
* **db:** 修复 checkpoints.db 体积膨胀导致无法启动的问题 ([#303](https://github.com/syrizelink/OpenFic/issues/303)) ([8c7cc10](https://github.com/syrizelink/OpenFic/commit/8c7cc1000ee2566845439be409eb4157c49e48cd))
* **desktop:** uv 安装 TLS 证书错误时自动重试 ([#292](https://github.com/syrizelink/OpenFic/issues/292)) ([79bad9b](https://github.com/syrizelink/OpenFic/commit/79bad9b56e3a149aa0e66b3ba842ba8a9abe4736))
* **frontend:** 修复 streamdown 流式渲染的最大更新深度崩溃问题 ([#272](https://github.com/syrizelink/OpenFic/issues/272)) ([ab4b9f5](https://github.com/syrizelink/OpenFic/commit/ab4b9f55c0e108998252747b0f54be6a5b62d2b4))
* **frontend:** 修复卡初始化的问题并增强连接失败诊断信息 ([#287](https://github.com/syrizelink/OpenFic/issues/287)) ([04acb43](https://github.com/syrizelink/OpenFic/commit/04acb43764c2b1261a2de7b4ee2a27acfed4e03b))
* **frontend:** 修复发送新消息后上一条 Assistant 轮次 toolbar 消失的问题 ([#273](https://github.com/syrizelink/OpenFic/issues/273)) ([ae8eda2](https://github.com/syrizelink/OpenFic/commit/ae8eda2d162e6e65057f20ecc1582055548789f7))
* **frontend:** 收起下拉框时不再误关闭设置面板 ([#297](https://github.com/syrizelink/OpenFic/issues/297)) ([c4e0b47](https://github.com/syrizelink/OpenFic/commit/c4e0b479a5642c7804dbdf68d448b913605284a1))
* **projects:** 修复项目列表加载不完全导致分页、搜索和排序失效的问题 ([#284](https://github.com/syrizelink/OpenFic/issues/284)) ([82af99e](https://github.com/syrizelink/OpenFic/commit/82af99e687ff0d57842a70489d39146eb5191059))


### ⚡ 性能优化

* **backend:** 优化检索索引状态与模型提供商列表接口性能 ([#291](https://github.com/syrizelink/OpenFic/issues/291)) ([c77b264](https://github.com/syrizelink/OpenFic/commit/c77b264eafc2c15e78793bd01d5cc32f6d7e4437))


### ✅ 测试

* **desktop:** 新增基于源码后端的本地开发模式 ([#304](https://github.com/syrizelink/OpenFic/issues/304)) ([84d63f1](https://github.com/syrizelink/OpenFic/commit/84d63f1aa6905896596818427f3f3275bcebc40e))
* **frontend:** 新增 Agent 会话生命周期 E2E 测试 ([#308](https://github.com/syrizelink/OpenFic/issues/308)) ([9478baf](https://github.com/syrizelink/OpenFic/commit/9478baf2f46317bd859deb21042c0bb02ce55441))

## [0.9.2](https://github.com/syrizelink/OpenFic/compare/v0.9.1...v0.9.2) (2026-08-08)


### 🐛 问题修复

* **agent_runtime:** 修复 LLM 调用无超时保护且盲目重试导致会话卡死的问题 ([#261](https://github.com/syrizelink/OpenFic/issues/261)) ([46535a0](https://github.com/syrizelink/OpenFic/commit/46535a0dbd652aad50369657d8e297aad3f4b48f))
* **agent:** 修复中断暂停状态的会话无法恢复的问题 ([#267](https://github.com/syrizelink/OpenFic/issues/267)) ([6029bc3](https://github.com/syrizelink/OpenFic/commit/6029bc37a53cff4054ed08f7dcca626b29398453))
* **agent:** 修复工具调用未并行执行的问题 ([#266](https://github.com/syrizelink/OpenFic/issues/266)) ([aefcd90](https://github.com/syrizelink/OpenFic/commit/aefcd90f1004f2bf8af887ff785d8532eb982492))
* **agent:** 限制智能体列表高度并支持滚动 ([#268](https://github.com/syrizelink/OpenFic/issues/268)) ([fa44696](https://github.com/syrizelink/OpenFic/commit/fa44696ea94d7b65c16e6d07f7a88642e3e8a7b2))
* **frontend:** 修复仪表盘图表日期范围与标签重叠的问题 ([#264](https://github.com/syrizelink/OpenFic/issues/264)) ([e3996ba](https://github.com/syrizelink/OpenFic/commit/e3996ba34703bb7e92b86b7e03f3feb6e98fe3c8))
* **frontend:** 修复同行内粘贴文本被拆分换行的问题 ([#258](https://github.com/syrizelink/OpenFic/issues/258)) ([45c3d6a](https://github.com/syrizelink/OpenFic/commit/45c3d6a19950dfd9f57c4d9bd3164f428453bba5))
* **frontend:** 修复移动端编辑器菜单点击无效导致复制粘贴不可用的问题 ([#260](https://github.com/syrizelink/OpenFic/issues/260)) ([ba4ba07](https://github.com/syrizelink/OpenFic/commit/ba4ba07c0e00723e400ec476d714abc476492174))


### ⚡ 性能优化

* **frontend:** 虚拟化 Agent 消息列表并合并流式增量渲染 ([#257](https://github.com/syrizelink/OpenFic/issues/257)) ([87aa448](https://github.com/syrizelink/OpenFic/commit/87aa448add26bce1dfb9dc925a6db72473d63ebd))
* **world-info:** 虚拟化世界书条目列表并优化拖拽排序 ([#254](https://github.com/syrizelink/OpenFic/issues/254)) ([ad94f34](https://github.com/syrizelink/OpenFic/commit/ad94f340c043999d5f8d6dc25580c559cec7edb0))


### 🔧 杂项

* **agent:** 添加会话计时器 ([#262](https://github.com/syrizelink/OpenFic/issues/262)) ([70e9652](https://github.com/syrizelink/OpenFic/commit/70e96528066389d7cb30329be6bbcd2d455f34e3))
* 添加压缩系统提示词选项 ([#263](https://github.com/syrizelink/OpenFic/issues/263)) ([5dbc83d](https://github.com/syrizelink/OpenFic/commit/5dbc83d2ef45ef341cd71b295664194a1934642d))

## [0.9.1](https://github.com/syrizelink/OpenFic/compare/v0.9.0...v0.9.1) (2026-08-05)


### 🐛 问题修复

* **agent:** 修复 ask_user 问题面板内容无法滚动的问题 ([#249](https://github.com/syrizelink/OpenFic/issues/249)) ([2921d0a](https://github.com/syrizelink/OpenFic/commit/2921d0aa743aaf418d07277bed9f59af67508f57))
* **backend:** 修复测试夹具重复初始化导致后端测试耗时过长的问题 ([#241](https://github.com/syrizelink/OpenFic/issues/241)) ([a355e7f](https://github.com/syrizelink/OpenFic/commit/a355e7f16a5afc14da98cc238fc4a021a9e73973))
* **desktop:** 修复 Socket 首次连接失败导致启动中断的问题 ([#248](https://github.com/syrizelink/OpenFic/issues/248)) ([7b84765](https://github.com/syrizelink/OpenFic/commit/7b847652037b165f3f7129e59c3564ce617a290c))
* **desktop:** 修复启动时窗口延迟显示的问题 ([#246](https://github.com/syrizelink/OpenFic/issues/246)) ([6d0e05f](https://github.com/syrizelink/OpenFic/commit/6d0e05f97753a3bcdd329be6f9a311b07714b4b6))
* **desktop:** 修复更新元数据缺失导致检查报错的问题 ([#239](https://github.com/syrizelink/OpenFic/issues/239)) ([3b77aab](https://github.com/syrizelink/OpenFic/commit/3b77aabe38134b34f46331d687fd0ca7ba4e8217))
* **index:** 修复分块配置保存使用旧输入值的问题 ([#250](https://github.com/syrizelink/OpenFic/issues/250)) ([ed75ce4](https://github.com/syrizelink/OpenFic/commit/ed75ce46a9be88a6044277d74abf5fe11123bf16))


### 👷 CI/CD

* **desktop:** 修复多架构构建导致发布包损坏的问题 ([#247](https://github.com/syrizelink/OpenFic/issues/247)) ([7ffe8cd](https://github.com/syrizelink/OpenFic/commit/7ffe8cd1a254e2c2b892bb806d6c83e75edd156f))

## [0.9.0](https://github.com/syrizelink/OpenFic/compare/v0.8.1...v0.9.0) (2026-08-04)


### ✨ 新功能

* **agent:** 支持用户消息图片附件输入 ([#229](https://github.com/syrizelink/OpenFic/issues/229)) ([2c12697](https://github.com/syrizelink/OpenFic/commit/2c126978b101dc3c76b43556e7017084f27f97f2))
* **desktop:** 添加壳层国际化支持 ([#223](https://github.com/syrizelink/OpenFic/issues/223)) ([90f26c1](https://github.com/syrizelink/OpenFic/commit/90f26c16a764c941124a3e70c8b2693b32a5f1d9))


### 🐛 问题修复

* **editor:** 修复移动端正文点击重复呼出键盘的问题 ([#226](https://github.com/syrizelink/OpenFic/issues/226)) ([79d03fa](https://github.com/syrizelink/OpenFic/commit/79d03fa3c9f32dc8183e7b2ce234d747c12bef5d))
* **providers:** 修复目录中部分提供商端点 URL 缺失的问题 ([#230](https://github.com/syrizelink/OpenFic/issues/230)) ([0006c90](https://github.com/syrizelink/OpenFic/commit/0006c906b8c878c07859d3e2b7afda02f4b2e2a1))
* **storage:** 清理数据库关联运行时数据 ([#238](https://github.com/syrizelink/OpenFic/issues/238)) ([b8d2ca5](https://github.com/syrizelink/OpenFic/commit/b8d2ca5d58d64ecaf2acee919a0638104b0dce72))
* **summary:** 修复跨卷删除章节导致区间摘要丢失的问题 ([#225](https://github.com/syrizelink/OpenFic/issues/225)) ([9ecaa07](https://github.com/syrizelink/OpenFic/commit/9ecaa07fb38e9eb845135aabe0336d21adc0966c))


### 🔧 杂项

* **desktop:** 添加桌面端菜单栏 ([#221](https://github.com/syrizelink/OpenFic/issues/221)) ([0d9bbe8](https://github.com/syrizelink/OpenFic/commit/0d9bbe8dc9f5cfb186cf2a196b40b4d577c113b1))

## [0.8.1](https://github.com/syrizelink/OpenFic/compare/v0.8.0...v0.8.1) (2026-07-31)


### 🐛 问题修复

* **agent:** 修复旧会话配置无法恢复的问题 ([#202](https://github.com/syrizelink/OpenFic/issues/202)) ([ac9a59b](https://github.com/syrizelink/OpenFic/commit/ac9a59bea251a6bed4fb4ffcde005e74ee665151))
* **agent:** 修复编辑工具转义空白匹配失败的问题 ([#214](https://github.com/syrizelink/OpenFic/issues/214)) ([649b87b](https://github.com/syrizelink/OpenFic/commit/649b87b801458bfd3b1c44e84215a299b8eaa174))
* **agent:** 修复重启后会话设置持续锁定的问题 ([#216](https://github.com/syrizelink/OpenFic/issues/216)) ([33555ff](https://github.com/syrizelink/OpenFic/commit/33555ff2c4d3a369938fd95e22fe64f276320a64))
* **dashboard:** 修复调用记录时间未转换时区的问题 ([#204](https://github.com/syrizelink/OpenFic/issues/204)) ([da977a8](https://github.com/syrizelink/OpenFic/commit/da977a8311b8effbed9506f204bb97eb2d8af6d7))
* **desktop:** 修复 macOS 运行时与安装包校验异常 ([#215](https://github.com/syrizelink/OpenFic/issues/215)) ([8ebac44](https://github.com/syrizelink/OpenFic/commit/8ebac44ab083b00b2de394f740badcc45c8773a0))
* **desktop:** 修复本地后端 Socket 代理连接失败的问题 ([#209](https://github.com/syrizelink/OpenFic/issues/209)) ([7ffbd78](https://github.com/syrizelink/OpenFic/commit/7ffbd78ea937e45a93d4faa571ef1434050f9f98))
* **frontend:** 新建角色后自动切换标签 ([#191](https://github.com/syrizelink/OpenFic/issues/191)) ([8f35b51](https://github.com/syrizelink/OpenFic/commit/8f35b51b38670982764b7615d64106d9944329ee))


### 🔧 杂项

* **editor:** 优化编辑器体验 ([#219](https://github.com/syrizelink/OpenFic/issues/219)) ([f3554d4](https://github.com/syrizelink/OpenFic/commit/f3554d47ea549dffebda9ad4f2289dc904cdfa6f))
* **provider:** 新增 Anthropic Compatible 提供商 ([#208](https://github.com/syrizelink/OpenFic/issues/208)) ([2000f79](https://github.com/syrizelink/OpenFic/commit/2000f79d522bd4140994bc3ce1c59799f85baa30))
* **skills:** 优化技能配置体验 ([#218](https://github.com/syrizelink/OpenFic/issues/218)) ([d7976c5](https://github.com/syrizelink/OpenFic/commit/d7976c583bdd3bf6d3a67c9efc3231b941d4c167))
* 优化角色和世界书列表体验 ([#212](https://github.com/syrizelink/OpenFic/issues/212)) ([191ed05](https://github.com/syrizelink/OpenFic/commit/191ed05888ced345ca4a0b78f58dfacc8b832ab4))

## [0.8.0](https://github.com/syrizelink/OpenFic/compare/v0.7.6...v0.8.0) (2026-07-29)


### ✨ 新功能

* **backend:** 为编辑工具引入模糊匹配与归一化机制 ([#165](https://github.com/syrizelink/OpenFic/issues/165)) ([5805078](https://github.com/syrizelink/OpenFic/commit/580507862debbe66d7ea221fc6deb339da71c211))
* **import:** 支持 TXT 分卷导入 ([#197](https://github.com/syrizelink/OpenFic/issues/197)) ([4c781ce](https://github.com/syrizelink/OpenFic/commit/4c781ce36a2baa4b5b1f8d2e82e51b72b659f28f))
* **writing:** 支持章节导出 ([#195](https://github.com/syrizelink/OpenFic/issues/195)) ([44171e8](https://github.com/syrizelink/OpenFic/commit/44171e86010c858540b2a23e78e11d01e1ef5532))


### 🐛 问题修复

* **agent:** 修复工具刷新失效问题 ([#185](https://github.com/syrizelink/OpenFic/issues/185)) ([905aae2](https://github.com/syrizelink/OpenFic/commit/905aae2574d2dd2dc15ffd771d0aa00f0cdc0c3e))
* **agent:** 修复跨页面切换导致的侧边栏状态丢失问题 ([#178](https://github.com/syrizelink/OpenFic/issues/178)) ([22b9a37](https://github.com/syrizelink/OpenFic/commit/22b9a37c018ab64828cc7fdb97cbc1fa2b923d7e))
* **agent:** 清理不可达的会话检查点 ([#184](https://github.com/syrizelink/OpenFic/issues/184)) ([8908120](https://github.com/syrizelink/OpenFic/commit/890812052a3542dd5a1e799753206d67f108cf54))
* **agent:** 避免中断会话普通消息状态冲突 ([#177](https://github.com/syrizelink/OpenFic/issues/177)) ([787669b](https://github.com/syrizelink/OpenFic/commit/787669b51dc6a6a1e6b34184a6acf3e38504d854))
* **backend:** 修复离线环境下的分词表加载失败的问题 ([#187](https://github.com/syrizelink/OpenFic/issues/187)) ([169d40b](https://github.com/syrizelink/OpenFic/commit/169d40b7410ef238f18cb669936e17473b7696cd))
* **ci:** 移除 PR 自查清单强制校验 ([#180](https://github.com/syrizelink/OpenFic/issues/180)) ([54df8c1](https://github.com/syrizelink/OpenFic/commit/54df8c1635f8ff1d7ba37f2289649ab0758af9bd))
* **ci:** 跳过发布 PR 检查 ([#174](https://github.com/syrizelink/OpenFic/issues/174)) ([2286422](https://github.com/syrizelink/OpenFic/commit/22864220d8f9732255587c3c921e0b21132a5d2d))
* **desktop:** 优化运行时连接流程 ([#199](https://github.com/syrizelink/OpenFic/issues/199)) ([83c78ad](https://github.com/syrizelink/OpenFic/commit/83c78ad119f3cc0c083fb15312af19673d3b4340))
* **desktop:** 修复系统缺失 tar 导致运行环境安装失败的问题 ([#188](https://github.com/syrizelink/OpenFic/issues/188)) ([9685c19](https://github.com/syrizelink/OpenFic/commit/9685c19d4058a3083a29d54dc00455110ab768de))
* **desktop:** 完善运行环境调试信息处理 ([#196](https://github.com/syrizelink/OpenFic/issues/196)) ([39f3e55](https://github.com/syrizelink/OpenFic/commit/39f3e55653e30d2cba7dece7425839a4ebae4d75))
* **frontend:** 修复编辑器剪贴板换行处理 ([#189](https://github.com/syrizelink/OpenFic/issues/189)) ([95daf32](https://github.com/syrizelink/OpenFic/commit/95daf32c59fc4931dd52dec07f7737e76661b676))
* **providers:** 避免图标请求阻塞连接操作 ([#183](https://github.com/syrizelink/OpenFic/issues/183)) ([70d9419](https://github.com/syrizelink/OpenFic/commit/70d9419832496b519ad629abf062fde3063d7b70))


### 🔧 杂项

* **agent:** 补充角色页 Agent 侧边栏 ([#176](https://github.com/syrizelink/OpenFic/issues/176)) ([ad4988e](https://github.com/syrizelink/OpenFic/commit/ad4988e85adedcc96911fca85338eff48daad488))
* **backend:** 为 OpenAI Compatible 提供商添加思考强度支持 ([#192](https://github.com/syrizelink/OpenFic/issues/192)) ([195615f](https://github.com/syrizelink/OpenFic/commit/195615f4e22f0c33442e96d072a726de7363599d))
* **editor:** 新增单条正文内容长度限制 ([#193](https://github.com/syrizelink/OpenFic/issues/193)) ([cb87f42](https://github.com/syrizelink/OpenFic/commit/cb87f42a8803584e664519696ddce6aca6883def))


### 👷 CI/CD

* 添加 PR 检查工作流 ([#172](https://github.com/syrizelink/OpenFic/issues/172)) ([17ce3f7](https://github.com/syrizelink/OpenFic/commit/17ce3f752348dd0c965ae9b6c360b48cedd7e22d))

## [0.7.6](https://github.com/syrizelink/OpenFic/compare/v0.7.5...v0.7.6) (2026-07-26)


### 🐛 问题修复

* **backend:** 修复Windows上后台任务事件无法实时同步的问题 ([#148](https://github.com/syrizelink/OpenFic/issues/148)) ([f4e83e1](https://github.com/syrizelink/OpenFic/commit/f4e83e1c2e8affb07029750c64d2d6bd0f1779b3))
* **backend:** 修复开发服务器运行时配置异常 ([#152](https://github.com/syrizelink/OpenFic/issues/152)) ([e5e93ec](https://github.com/syrizelink/OpenFic/commit/e5e93ec324ca28ae0e6e06e698c59e97367da7b8))
* **backend:** 修复部分提供商流式 token 用量缺失的问题 ([#158](https://github.com/syrizelink/OpenFic/issues/158)) ([16376e9](https://github.com/syrizelink/OpenFic/commit/16376e9baa618cc91ce74217f5a354e74ec01d9f))
* **desktop:** 修复桌面端主题与字体无法跟随前端同步的问题 ([#157](https://github.com/syrizelink/OpenFic/issues/157)) ([a2f8ebf](https://github.com/syrizelink/OpenFic/commit/a2f8ebf495a67fa68d30c181fcdcdc6bd4afe70f))


### 📚 文档

* 更新 README 章节结构 ([#155](https://github.com/syrizelink/OpenFic/issues/155)) ([154fab7](https://github.com/syrizelink/OpenFic/commit/154fab748fd17b448cba173821234b7bc0acf70c))


### 🔧 杂项

* **desktop:** 添加窗口状态记忆能力 ([#159](https://github.com/syrizelink/OpenFic/issues/159)) ([eb0e1a4](https://github.com/syrizelink/OpenFic/commit/eb0e1a4816bcd6d9b0682a8c96190eb52e3fc3a6))
* 添加结构化 Issue 模板 ([#156](https://github.com/syrizelink/OpenFic/issues/156)) ([9e3b8ad](https://github.com/syrizelink/OpenFic/commit/9e3b8ad04912331507efa742d9963b7f1ed72883))

## [0.7.5](https://github.com/syrizelink/OpenFic/compare/v0.7.4...v0.7.5) (2026-07-26)


### 🐛 问题修复

* **agent:** 修复会话结束后设置仍锁定的问题 ([#137](https://github.com/syrizelink/OpenFic/issues/137)) ([103c392](https://github.com/syrizelink/OpenFic/commit/103c392043f2eb246a974e431e40d0e15058a391))
* **backend:** 修复 Ollama Cloud 地址覆盖导致的模型调用失败问题 ([#146](https://github.com/syrizelink/OpenFic/issues/146)) ([b5d116d](https://github.com/syrizelink/OpenFic/commit/b5d116d065dfa9db24ee8635a8d97b6cb8e2e9cd))
* **backend:** 修复 Windows 后台任务队列阻塞的问题 ([#147](https://github.com/syrizelink/OpenFic/issues/147)) ([cf1ffa1](https://github.com/syrizelink/OpenFic/commit/cf1ffa1e0c7b47e1c38c7a7019bcb8e91f38791f))
* **desktop:** 为桌面端运行环境添加国内下载源 ([#126](https://github.com/syrizelink/OpenFic/issues/126)) ([5ba142e](https://github.com/syrizelink/OpenFic/commit/5ba142e50d5fef9f6f425d56cc5612264fe09d14))
* **frontend:** 修复世界书开关状态错乱的问题 ([#138](https://github.com/syrizelink/OpenFic/issues/138)) ([7d5eb27](https://github.com/syrizelink/OpenFic/commit/7d5eb27da67edb5fdb3cc0aed4649a10892c08ae))
* **frontend:** 修复已删除项目仍可打开的问题 ([#129](https://github.com/syrizelink/OpenFic/issues/129)) ([0542e8f](https://github.com/syrizelink/OpenFic/commit/0542e8faeab65ae34292ac6d329a61e7772a4e68))
* **frontend:** 修复提示词编辑内容丢失和本地修改提示缺失的问题 ([#140](https://github.com/syrizelink/OpenFic/issues/140)) ([954d552](https://github.com/syrizelink/OpenFic/commit/954d5529c5941ac3172cf5a3b6b1d1cb636431db))
* **frontend:** 修复桌面端后端资源地址解析异常 ([#136](https://github.com/syrizelink/OpenFic/issues/136)) ([09c570f](https://github.com/syrizelink/OpenFic/commit/09c570f4ac0b96b88427eed48de76da80ef9e525))
* **frontend:** 取消提供商任务类型筛选 ([#143](https://github.com/syrizelink/OpenFic/issues/143)) ([f582c8e](https://github.com/syrizelink/OpenFic/commit/f582c8ef1b4bd98e3e3ee4f461fb4e0341f7ed23))
* **storage:** 修复章节排序更新冲突 ([#141](https://github.com/syrizelink/OpenFic/issues/141)) ([dade8e8](https://github.com/syrizelink/OpenFic/commit/dade8e899dbddf6ae8ab8eae190aa1a3e81be034))


### 🔧 杂项

* **frontend:** 添加系统默认字体选项 ([#128](https://github.com/syrizelink/OpenFic/issues/128)) ([3980ee2](https://github.com/syrizelink/OpenFic/commit/3980ee2af3d85c66016b0d2ada45c7058596ef8c))

## [0.7.4](https://github.com/syrizelink/OpenFic/compare/v0.7.3...v0.7.4) (2026-07-25)


### 🐛 问题修复

* **agent:** 优化会话运行状态提示 ([#122](https://github.com/syrizelink/OpenFic/issues/122)) ([04c6e2e](https://github.com/syrizelink/OpenFic/commit/04c6e2e6639c21594a90c9d5d9a5fe607c7a9dcc))
* **agent:** 优化用户消息展开动画 ([#120](https://github.com/syrizelink/OpenFic/issues/120)) ([00d9cc8](https://github.com/syrizelink/OpenFic/commit/00d9cc89a12984462f5a8eb80d0b3d372aa22446))
* **agent:** 修复回滚时卷章节数不同步的问题 ([#117](https://github.com/syrizelink/OpenFic/issues/117)) ([0e9bf90](https://github.com/syrizelink/OpenFic/commit/0e9bf908fb4f323f8737bcd7866ac54c4130e669))
* **agent:** 修复异常消息导致的僵尸会话 ([#123](https://github.com/syrizelink/OpenFic/issues/123)) ([84b95fe](https://github.com/syrizelink/OpenFic/commit/84b95fec91a65679d4f7a729515c4012b011af06))
* **agent:** 修复流式消息底部跟随失效的问题 ([#119](https://github.com/syrizelink/OpenFic/issues/119)) ([d79d3ed](https://github.com/syrizelink/OpenFic/commit/d79d3edc1e6e967dd20752645bc52c0e95fe6bb8))
* **agent:** 完善子智能体工具状态展示 ([#118](https://github.com/syrizelink/OpenFic/issues/118)) ([a908536](https://github.com/syrizelink/OpenFic/commit/a9085361cc32b46cc689c51a8d400c03ba0a1592))
* **frontend:** 防止写作编辑内容丢失 ([#116](https://github.com/syrizelink/OpenFic/issues/116)) ([06698db](https://github.com/syrizelink/OpenFic/commit/06698dbb1a400b3cebadc7f237527dc53aa0e0e5))


### 📚 文档

* **readme:** 同步项目文档内容 ([#124](https://github.com/syrizelink/OpenFic/issues/124)) ([736779c](https://github.com/syrizelink/OpenFic/commit/736779cebea82f1c69e699d887a6a76c9cda2ef8))


### 🔧 杂项

* **agent:** 调整内置智能体定义 ([#115](https://github.com/syrizelink/OpenFic/issues/115)) ([3dcdbb8](https://github.com/syrizelink/OpenFic/commit/3dcdbb82255e79a10059b69f8c3a41d966a8ed5e))
* **agent:** 调整内置智能体提示词 ([#121](https://github.com/syrizelink/OpenFic/issues/121)) ([211c7b0](https://github.com/syrizelink/OpenFic/commit/211c7b04f687bac675c6700ebe503fb598b4e73a))
* **skill:** 添加内置写作技能 ([#113](https://github.com/syrizelink/OpenFic/issues/113)) ([664d126](https://github.com/syrizelink/OpenFic/commit/664d12632b63b8c363bc3ead66a1197a8ff56826))

## [0.7.3](https://github.com/syrizelink/OpenFic/compare/v0.7.2...v0.7.3) (2026-07-19)


### 🐛 问题修复

* **agent:** 修复子智能体派发配置 ([#111](https://github.com/syrizelink/OpenFic/issues/111)) ([8906741](https://github.com/syrizelink/OpenFic/commit/89067410aee4246a7a912e61bfba46f50aeef946))
* **backend:** 修复会话标题生成异常 ([#108](https://github.com/syrizelink/OpenFic/issues/108)) ([429ee53](https://github.com/syrizelink/OpenFic/commit/429ee53f10f6f9cd3723b758259c833b4d708316))


### ♻️ 代码重构

* **agent:** 重构 Agent 工具上下文与中断恢复链路 ([#110](https://github.com/syrizelink/OpenFic/issues/110)) ([5ab5a2b](https://github.com/syrizelink/OpenFic/commit/5ab5a2bc722267ff0e7af7e13e5b1f1c4bc2de78))
* **dashboard:** 调用记录详情存储优化并记录工具引用 ([#107](https://github.com/syrizelink/OpenFic/issues/107)) ([c25b2c1](https://github.com/syrizelink/OpenFic/commit/c25b2c16673e860e8e0df3d614cec5169f3a2ff7))
* **model:** 统一高级参数配置 ([#109](https://github.com/syrizelink/OpenFic/issues/109)) ([f672970](https://github.com/syrizelink/OpenFic/commit/f672970f13567721b2ce6d731419e0ee1214a2e4))


### 🔧 杂项

* **agent:** 本地化适配工具权限展示文案 ([#112](https://github.com/syrizelink/OpenFic/issues/112)) ([362c129](https://github.com/syrizelink/OpenFic/commit/362c12903beee21373e9db124f6fafb5b08dfb41))
* **backend:** 调整摘要上下文结构 ([#106](https://github.com/syrizelink/OpenFic/issues/106)) ([6b2cf6d](https://github.com/syrizelink/OpenFic/commit/6b2cf6d8376e61daee7902a796dcda73342ade28))
* **frontend:** 添加最近打开项目入口 ([#104](https://github.com/syrizelink/OpenFic/issues/104)) ([16d6f4b](https://github.com/syrizelink/OpenFic/commit/16d6f4bb5b45edee3e1876c95e0783aea15a2f91))

## [0.7.2](https://github.com/syrizelink/OpenFic/compare/v0.7.1...v0.7.2) (2026-07-15)


### 🐛 问题修复

* **desktop:** 修复更新日志渲染 ([#102](https://github.com/syrizelink/OpenFic/issues/102)) ([2b75f25](https://github.com/syrizelink/OpenFic/commit/2b75f25b1d08ecccbc4e9b7bee1e727b21fe24bf))

## [0.7.1](https://github.com/syrizelink/OpenFic/compare/v0.7.0...v0.7.1) (2026-07-14)


### 🐛 问题修复

* **release:** 统一跨平台产物命名 ([#100](https://github.com/syrizelink/OpenFic/issues/100)) ([56def22](https://github.com/syrizelink/OpenFic/commit/56def22bf42fa660b0b1459929c7f928f1e02c09))

## [0.7.0](https://github.com/syrizelink/OpenFic/compare/v0.6.2...v0.7.0) (2026-07-14)


### ✨ 新功能

* **desktop:** 支持应用内自动更新 ([#99](https://github.com/syrizelink/OpenFic/issues/99)) ([bcd6eb9](https://github.com/syrizelink/OpenFic/commit/bcd6eb94fe846c4237b89ffdad87d620ec7706b0))


### 🔧 杂项

* **build:** 迁移前端与桌面端构建至 Vite+ ([#97](https://github.com/syrizelink/OpenFic/issues/97)) ([c77fd90](https://github.com/syrizelink/OpenFic/commit/c77fd907ce9a0a55eac24e3fc49094c03c188a25))

## [0.6.2](https://github.com/syrizelink/OpenFic/compare/v0.6.1...v0.6.2) (2026-07-13)


### 🐛 问题修复

* **agent:** 修复会话切换模型不生效 ([#91](https://github.com/syrizelink/OpenFic/issues/91)) ([26ef7f3](https://github.com/syrizelink/OpenFic/commit/26ef7f3beb202eb182b56ed483c144852be6d9c6))
* **agent:** 修复会话重连后流式事件丢失 ([#94](https://github.com/syrizelink/OpenFic/issues/94)) ([018749c](https://github.com/syrizelink/OpenFic/commit/018749caeea11f98d5f8405f17f7868949b3dbba))
* **agent:** 防止会话检查点泄露模型密钥 ([#92](https://github.com/syrizelink/OpenFic/issues/92)) ([0342427](https://github.com/syrizelink/OpenFic/commit/034242754890db39d2296f3b489c2c2317eb37e7))
* **mobile:** 修复移动端布局适配问题 ([#96](https://github.com/syrizelink/OpenFic/issues/96)) ([f396b34](https://github.com/syrizelink/OpenFic/commit/f396b34066577be9a9a3e5bbef4ace3192b7b1f4))
* **settings:** 锁定运行期间的智能体配置 ([#93](https://github.com/syrizelink/OpenFic/issues/93)) ([6afd4b0](https://github.com/syrizelink/OpenFic/commit/6afd4b0e9fa8c106917e8d3ec07f32255c30f7e4))


### ♻️ 代码重构

* **prompt-chains:** 重构提示词管理页面 ([#95](https://github.com/syrizelink/OpenFic/issues/95)) ([73db522](https://github.com/syrizelink/OpenFic/commit/73db52232f506edb9bda8e76156382aef4508310))


### 🔧 杂项

* **agent:** 限制子智能体委派与提问能力 ([#90](https://github.com/syrizelink/OpenFic/issues/90)) ([9999283](https://github.com/syrizelink/OpenFic/commit/999928376012548bfca968aab270f38e7bcd3a83))
* **models:** 优化模型选择器并移除Provider图标上传 ([#87](https://github.com/syrizelink/OpenFic/issues/87)) ([436f761](https://github.com/syrizelink/OpenFic/commit/436f761611ee57c67bcf0cdad72284b85a9fafaf))
* **providers:** 优化内置提供商选取、刷新与调用 ([#89](https://github.com/syrizelink/OpenFic/issues/89)) ([0fe4188](https://github.com/syrizelink/OpenFic/commit/0fe418852730254789473fdcd96993136f7dabc2))

## [0.6.1](https://github.com/syrizelink/OpenFic/compare/v0.6.0...v0.6.1) (2026-07-11)


### 🐛 问题修复

* **backend:** 去重会话标题后台任务 ([#82](https://github.com/syrizelink/OpenFic/issues/82)) ([afd9650](https://github.com/syrizelink/OpenFic/commit/afd96506fff12d006383bedaae83c8273349a8c6))
* **background:** 修复孤儿后台任务无法自动清理的问题 ([#83](https://github.com/syrizelink/OpenFic/issues/83)) ([643531d](https://github.com/syrizelink/OpenFic/commit/643531d73f86a860832305651bdc03a829ba136b))
* **frontend:** 修复规则编辑区布局 ([#85](https://github.com/syrizelink/OpenFic/issues/85)) ([025efad](https://github.com/syrizelink/OpenFic/commit/025efad2f6ddf624b7d37242bfd180f8fa1ad4e2))
* **index:** 修复索引取消清理与轮询导致的性能问题 ([#86](https://github.com/syrizelink/OpenFic/issues/86)) ([73fa08e](https://github.com/syrizelink/OpenFic/commit/73fa08e0f2c7e8049058e085837a45feb5cfeb28))


### ♻️ 代码重构

* **agent:** 重构 mention XML 流转链路 ([#78](https://github.com/syrizelink/OpenFic/issues/78)) ([28e7b16](https://github.com/syrizelink/OpenFic/commit/28e7b16aeb6c9d8288cd2d27210f075883a5d0ac))
* **agent:** 重构 Skill 功能 ([#77](https://github.com/syrizelink/OpenFic/issues/77)) ([97e1f5e](https://github.com/syrizelink/OpenFic/commit/97e1f5e20083de7b2f1ca22073bbbd42314abe9c))
* **index:** 重构索引面板与进度展示 ([#80](https://github.com/syrizelink/OpenFic/issues/80)) ([eff0886](https://github.com/syrizelink/OpenFic/commit/eff0886281ac277ccc49e03ab6cba8c3ec0c2eb3))
* **summary:** 重构摘要生成面板与交互体验 ([#84](https://github.com/syrizelink/OpenFic/issues/84)) ([8e16a19](https://github.com/syrizelink/OpenFic/commit/8e16a19204ff9718fcf7a25b38719a80c9c2cf52))


### 📚 文档

* 更新README ([#79](https://github.com/syrizelink/OpenFic/issues/79)) ([869b98c](https://github.com/syrizelink/OpenFic/commit/869b98c248dd442c96165a47883b2ff011d697df))


### 🔧 杂项

* **frontend:** 适配角色与世界书移动端顶栏 ([#74](https://github.com/syrizelink/OpenFic/issues/74)) ([1824117](https://github.com/syrizelink/OpenFic/commit/1824117893de708fe7c802379021885236e2ea2b))
* **status-bar:** 添加索引进度展示 ([#81](https://github.com/syrizelink/OpenFic/issues/81)) ([84f94c7](https://github.com/syrizelink/OpenFic/commit/84f94c725854e42d1e3a80cff82c707ebe30b643))

## [0.6.0](https://github.com/syrizelink/OpenFic/compare/v0.5.0...v0.6.0) (2026-07-07)


### ✨ 新功能

* **agent:** 添加角色工具与回滚支持 ([#70](https://github.com/syrizelink/OpenFic/issues/70)) ([4d2bbf0](https://github.com/syrizelink/OpenFic/commit/4d2bbf06bef79b9fd97f2be414c6a5b779c5c865))
* **characters:** 添加角色管理功能 ([#64](https://github.com/syrizelink/OpenFic/issues/64)) ([1d1626a](https://github.com/syrizelink/OpenFic/commit/1d1626a316c5bcd0471f54807ae29a1ee81df918))
* **frontend:** 添加全局状态栏 ([#71](https://github.com/syrizelink/OpenFic/issues/71)) ([d584d56](https://github.com/syrizelink/OpenFic/commit/d584d560a6e05747655a4538593da48eaee87fbe))


### ♻️ 代码重构

* **frontend:** 将仪表盘图表库替换为 Nivo ([#72](https://github.com/syrizelink/OpenFic/issues/72)) ([3cbd4b7](https://github.com/syrizelink/OpenFic/commit/3cbd4b7389e39bf80d26d7ac8a24a85ae1a39a05))


### 🔧 杂项

* **api:** 世界书改为项目强绑定 ([#73](https://github.com/syrizelink/OpenFic/issues/73)) ([393add6](https://github.com/syrizelink/OpenFic/commit/393add677c755ddd60bf1019ebd6110b75b462b3))
* **backend:** 添加 justfile 后端命令封装 ([#69](https://github.com/syrizelink/OpenFic/issues/69)) ([d66b128](https://github.com/syrizelink/OpenFic/commit/d66b1282ef7a4934a11827e793b894937f0cfc86))
* **backend:** 迁移类型检查到 ty ([#68](https://github.com/syrizelink/OpenFic/issues/68)) ([d404696](https://github.com/syrizelink/OpenFic/commit/d40469688379706a176958cf6407d747a8c6b85c))
* **frontend:** 添加 Oxfmt 格式化支持 ([#67](https://github.com/syrizelink/OpenFic/issues/67)) ([40e2efd](https://github.com/syrizelink/OpenFic/commit/40e2efd7890749378e76958d85a9da0819789fdf))
* **frontend:** 迁移前端检查到 Oxlint ([#66](https://github.com/syrizelink/OpenFic/issues/66)) ([7c10648](https://github.com/syrizelink/OpenFic/commit/7c10648bcd31ab6f71248e8af5aa4d0f7414ac51))

## [0.5.0](https://github.com/syrizelink/OpenFic/compare/v0.4.9...v0.5.0) (2026-07-04)


### ✨ 新功能

* **agent:** 支持世界书条目与回滚 ([#59](https://github.com/syrizelink/OpenFic/issues/59)) ([b02549d](https://github.com/syrizelink/OpenFic/commit/b02549d8ab8dc050478f98d8e95601c95ade3295))
* **frontend:** 添加 PWA 支持实现可安装应用 ([#56](https://github.com/syrizelink/OpenFic/issues/56)) ([bd623fb](https://github.com/syrizelink/OpenFic/commit/bd623fb73c87733a58e3d521cf9f066bcc0ccde7))


### 🐛 问题修复

* **agent:** 修复 subagent 回滚状态恢复 ([#60](https://github.com/syrizelink/OpenFic/issues/60)) ([b5fa608](https://github.com/syrizelink/OpenFic/commit/b5fa60852a1031f9626e0fff201b719da77cb4c0))
* **frontend:** 修复 Agent 消息完成重新挂载的问题 ([#61](https://github.com/syrizelink/OpenFic/issues/61)) ([10e2e53](https://github.com/syrizelink/OpenFic/commit/10e2e53811853d2b26c1bcdec5dd1152a02f1223))
* **frontend:** 修复 Agent 消息流式展示顺序 ([#63](https://github.com/syrizelink/OpenFic/issues/63)) ([9b4ee74](https://github.com/syrizelink/OpenFic/commit/9b4ee74f4e0f0481cba5f5c021ca0b61aa06c0f9))
* **frontend:** 调整 Agent 工具消息展示 ([#62](https://github.com/syrizelink/OpenFic/issues/62)) ([f6ccfbb](https://github.com/syrizelink/OpenFic/commit/f6ccfbb2d853ac009a13def1b96d5cad1043cffa))


### 🔧 杂项

* 调整 Agent 会话命名与任务列表交互 ([#58](https://github.com/syrizelink/OpenFic/issues/58)) ([741d2e3](https://github.com/syrizelink/OpenFic/commit/741d2e369a37c11d28f3831fd5eb5d777b09ab46))

## [0.4.9](https://github.com/syrizelink/OpenFic/compare/v0.4.8...v0.4.9) (2026-07-02)


### 🐛 问题修复

* **assistant:** 使用稳定的 diff section type ([#50](https://github.com/syrizelink/OpenFic/issues/50)) ([27decdc](https://github.com/syrizelink/OpenFic/commit/27decdcdf4bfe1fb6404d73a552fa1cc53958876))
* **frontend:** 修复 Agent 侧边栏模型图标显示 ([#54](https://github.com/syrizelink/OpenFic/issues/54)) ([9eeaaff](https://github.com/syrizelink/OpenFic/commit/9eeaaff74c83a8d492eeb8fd3aa096017a89804c))
* **frontend:** 对齐 Agent 工具消息注册 ([#55](https://github.com/syrizelink/OpenFic/issues/55)) ([b7942f5](https://github.com/syrizelink/OpenFic/commit/b7942f5cab56836dbeb3f837e4e6ad5deff373b3))


### 🔧 杂项

* **frontend:** 统一设置面板加载行为 ([#52](https://github.com/syrizelink/OpenFic/issues/52)) ([798e8ad](https://github.com/syrizelink/OpenFic/commit/798e8add8df5d24c93bbf0d1118049f6b4412ea4))
* **frontend:** 补齐前端界面 i18n 文案接入 ([#51](https://github.com/syrizelink/OpenFic/issues/51)) ([7932bf7](https://github.com/syrizelink/OpenFic/commit/7932bf7e4f3175746677f1be990164ca64e3bc24))
* **frontend:** 调整设置面板模型禁用态 ([#53](https://github.com/syrizelink/OpenFic/issues/53)) ([86449ec](https://github.com/syrizelink/OpenFic/commit/86449ece001aa8dbf210d322d19522ed81d8f620))


### 👷 CI/CD

* **release:** 修复每次 PR 都触发发版 ([#48](https://github.com/syrizelink/OpenFic/issues/48)) ([5668036](https://github.com/syrizelink/OpenFic/commit/5668036edb098c386ec8369867f21e21c9b0bd60))

## [0.4.8](https://github.com/syrizelink/OpenFic/compare/v0.4.7...v0.4.8) (2026-07-01)


### 🔧 杂项

* **frontend:** 调整设置面板自动保存 ([#46](https://github.com/syrizelink/OpenFic/issues/46)) ([a94d0eb](https://github.com/syrizelink/OpenFic/commit/a94d0ebf7683e2b864c5ba3539ede0f38bce66e9))

## [0.4.7](https://github.com/syrizelink/OpenFic/compare/v0.4.6...v0.4.7) (2026-07-01)


### 🐛 问题修复

* **desktop:** 修复本地后端启动 ([#43](https://github.com/syrizelink/OpenFic/issues/43)) ([12440f7](https://github.com/syrizelink/OpenFic/commit/12440f715495a2755c81a7be794426ca2cb7027b))

## [0.4.6](https://github.com/syrizelink/OpenFic/compare/v0.4.5...v0.4.6) (2026-07-01)


### 🐛 问题修复

* **desktop:** 修复本地运行时安装 ([#41](https://github.com/syrizelink/OpenFic/issues/41)) ([f77988b](https://github.com/syrizelink/OpenFic/commit/f77988ba27449fb0708bfcce6395027f4e067ea3))

## [0.4.5](https://github.com/syrizelink/OpenFic/compare/v0.4.4...v0.4.5) (2026-07-01)


### 👷 CI/CD

* **package:** 优化发布缓存复用 ([#39](https://github.com/syrizelink/OpenFic/issues/39)) ([68f9542](https://github.com/syrizelink/OpenFic/commit/68f954246c1e1f9307313cda7c8e8f6082be2f8b))

## [0.4.4](https://github.com/syrizelink/OpenFic/compare/v0.4.3...v0.4.4) (2026-07-01)


### 🐛 问题修复

* **desktop:** 修复 Windows 构建样式解析 ([#37](https://github.com/syrizelink/OpenFic/issues/37)) ([e837bb1](https://github.com/syrizelink/OpenFic/commit/e837bb14ea17d2a3ef46b0de6d6a72590f3778a9))

## [0.4.3](https://github.com/syrizelink/OpenFic/compare/v0.4.2...v0.4.3) (2026-07-01)


### 👷 CI/CD

* **release:** 等待 release PR 可合并 ([#35](https://github.com/syrizelink/OpenFic/issues/35)) ([6105251](https://github.com/syrizelink/OpenFic/commit/6105251aa84f173ca9eb998dd229e05e5f243ac2))

## [0.4.2](https://github.com/syrizelink/OpenFic/compare/v0.4.1...v0.4.2) (2026-07-01)


### 🐛 问题修复

* **ci:** 修复桌面发布流程 ([#33](https://github.com/syrizelink/OpenFic/issues/33)) ([9f100fc](https://github.com/syrizelink/OpenFic/commit/9f100fc8c4ab75f09f5fd5262cfbe7ca66e62353))

## [0.4.1](https://github.com/syrizelink/OpenFic/compare/v0.4.0...v0.4.1) (2026-07-01)


### 🐛 问题修复

* **ci:** 调整发布打包流程 ([#31](https://github.com/syrizelink/OpenFic/issues/31)) ([f83451a](https://github.com/syrizelink/OpenFic/commit/f83451a76225daa2c4d1669e93ef9f7f5309f52b))

## [0.4.0](https://github.com/syrizelink/OpenFic/compare/v0.3.3...v0.4.0) (2026-07-01)


### ✨ 新功能

* **desktop:** 添加桌面端应用 ([#29](https://github.com/syrizelink/OpenFic/issues/29)) ([77c7789](https://github.com/syrizelink/OpenFic/commit/77c7789e322b3a7ee029c4837272bf8a7c10df28))

## [0.3.3](https://github.com/syrizelink/OpenFic/compare/v0.3.2...v0.3.3) (2026-06-30)


### 🐛 问题修复

* **backend:** 完善后端分发构建与启动入口 ([86b3d77](https://github.com/syrizelink/OpenFic/commit/86b3d77baff1a5cc5d57e1617fc6e619eb1090d0))
* **backend:** 完善后端构建与分发流程 ([#27](https://github.com/syrizelink/OpenFic/issues/27)) ([86b3d77](https://github.com/syrizelink/OpenFic/commit/86b3d77baff1a5cc5d57e1617fc6e619eb1090d0))
* **backend:** 完善后端构建与分发流程 ([#27](https://github.com/syrizelink/OpenFic/issues/27)) ([86b3d77](https://github.com/syrizelink/OpenFic/commit/86b3d77baff1a5cc5d57e1617fc6e619eb1090d0))


### ♻️ 代码重构

* **backend:** 统一后台运行日志输出 ([86b3d77](https://github.com/syrizelink/OpenFic/commit/86b3d77baff1a5cc5d57e1617fc6e619eb1090d0))


### 📚 文档

* **readme:** 更新项目介绍与发布提示 ([86b3d77](https://github.com/syrizelink/OpenFic/commit/86b3d77baff1a5cc5d57e1617fc6e619eb1090d0))

## [0.3.2](https://github.com/syrizelink/OpenFic/compare/v0.3.1...v0.3.2) (2026-06-29)


### 🐛 问题修复

* **frontend:** 完善移动端适配 ([#25](https://github.com/syrizelink/OpenFic/issues/25)) ([a971904](https://github.com/syrizelink/OpenFic/commit/a971904f00466b53203aa87fb146330aad5e710a))

## [0.3.1](https://github.com/syrizelink/OpenFic/compare/v0.3.0...v0.3.1) (2026-06-29)


### 🐛 问题修复

* **ci:** 等待 release PR 可合并后再自动合并 ([#23](https://github.com/syrizelink/OpenFic/issues/23)) ([d868fc6](https://github.com/syrizelink/OpenFic/commit/d868fc6647d0f5cd8097f3e19c55a4f1c8546233))

## [0.3.0](https://github.com/syrizelink/OpenFic/compare/v0.2.6...v0.3.0) (2026-06-29)


### ✨ 新功能

* **frontend:** 补齐前端国际化文案并对齐英文翻译 ([#21](https://github.com/syrizelink/OpenFic/issues/21)) ([59d4249](https://github.com/syrizelink/OpenFic/commit/59d4249bfdfdb2b5867a789a7951e5812de8a011))

## [0.2.6](https://github.com/syrizelink/OpenFic/compare/v0.2.5...v0.2.6) (2026-06-29)


### 🐛 问题修复

* **ci:** 同步 uv.lock 并修正后端包名 ([#19](https://github.com/syrizelink/OpenFic/issues/19)) ([344bd82](https://github.com/syrizelink/OpenFic/commit/344bd82c5ac43ad85203f8d09ad340e5e4d46e18))

## [0.2.5](https://github.com/syrizelink/OpenFic/compare/v0.2.4...v0.2.5) (2026-06-29)


### 🐛 问题修复

* **ci:** 修复 release-please 未更新后端版本号及镜像版本 ([#17](https://github.com/syrizelink/OpenFic/issues/17)) ([de2bbdc](https://github.com/syrizelink/OpenFic/commit/de2bbdc611cfb2615bc5be1987d4a82066dcd6e9))

## [0.2.4](https://github.com/syrizelink/OpenFic/compare/v0.2.3...v0.2.4) (2026-06-29)


### 🐛 问题修复

* **agent:** 移除子计划依赖并改用笔记大纲 ([#15](https://github.com/syrizelink/OpenFic/issues/15)) ([da97a8b](https://github.com/syrizelink/OpenFic/commit/da97a8be36256a814677a20d540f853713f496f5))

## [0.2.3](https://github.com/syrizelink/OpenFic/compare/v0.2.2...v0.2.3) (2026-06-28)


### 🐛 问题修复

* **build:** 修正 electron-builder 配置并启用 changelog 作者显示 ([#13](https://github.com/syrizelink/OpenFic/issues/13)) ([82532ee](https://github.com/syrizelink/OpenFic/commit/82532ee37eb92e6965056b0e56c41c9a37fbbc8b))

## [0.2.2](https://github.com/syrizelink/OpenFic/compare/v0.2.1...v0.2.2) (2026-06-28)


### 🐛 问题修复

* **ci:** 修复 Docker 推送 403 与版本号同步缺失 ([ed002f5](https://github.com/syrizelink/OpenFic/commit/ed002f5e276402f5302675fa4ff6688c2acdc6a4))

## [0.2.1](https://github.com/syrizelink/OpenFic/compare/v0.2.0...v0.2.1) (2026-06-28)


### 🐛 问题修复

* **test:** 移除引用已迁移路径与偶发卡死的失效测试 ([eb638df](https://github.com/syrizelink/OpenFic/commit/eb638df74a1754c65351ec924098edabd7c15ebe))

## [0.2.0](https://github.com/syrizelink/OpenFic/compare/v0.1.0...v0.2.0) (2026-06-28)


### ✨ 新功能

* 完善项目 README 文档 ([ca919a2](https://github.com/syrizelink/OpenFic/commit/ca919a2f376937da1cd7aa8179a735bf45c8896c))


### 🐛 问题修复

* **ci:** 修复 release PR 合并命令参数解析 ([cf42194](https://github.com/syrizelink/OpenFic/commit/cf421944b77747de1b4c78b8925621d85e74f461))
* **ci:** 修正 release-please manifest 配置结构 ([3bf931b](https://github.com/syrizelink/OpenFic/commit/3bf931bdc53f244f01faf8115dca453e3232dd18))
* **ci:** 合并 release PR 前增加 checkout ([e1bf61a](https://github.com/syrizelink/OpenFic/commit/e1bf61a01fc477a73076d77b433fd42113bf1c2f))
