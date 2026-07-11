# Changelog

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
