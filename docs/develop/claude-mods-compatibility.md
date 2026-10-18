# 官方 Claude Mods 兼容性验证

2026-10-18，在隔离的 OpenFic 后端和生产静态前端中测试了官方仓库的全部三个 Mod。固定版本为 [569c5283d9a0a7ee7938df85bb32e4f48cbb8c86](https://github.com/anthropics/claude-code-playground/tree/569c5283d9a0a7ee7938df85bb32e4f48cbb8c86/claude-code/mods)，三个插件均为 `0.1.0`。

测试直接将官方目录打包成 ZIP，通过插件管理页面安装，未修改官方 manifest、hooks 配置或 MJS 源码。测试前逐个检查 SHA256；仓库保存了相同源码的离线 fixture、来源记录和 Apache-2.0 许可证。

## 结果

| Mod | 安装、启用 | 功能结果 |
| --- | --- | --- |
| Token Weather | 成功 | 在真实对话的输入框上方显示紧凑天气条、上下文用量与趋势。空内容高度为零；不生成独立侧栏页面入口。 |
| Replay Theater | 成功 | 在同一对话界面展开回放面板，保留 URL、消息与未发送草稿。原生章节创建和正文编辑形成两步回放；验证了 Prev/Next、Close、快捷键与 Escape。 |
| Blast Radius | 成功 | 核心功能不兼容。OpenFic 没有内置 Bash 工具，也没有为 Mod 开放 `$.process`；管理页和插件页面明确显示限制。没有验证实际 shell 命令的预览、等待确认和放行。 |

原实现中，三个包也都能安装启用，但 Token Weather 因缺少用量接口而没有内容，Replay Theater 的 Claude 工具名与本项目工具不匹配；Blast Radius 也没有明确的依赖警告。此次修复的是宿主适配层，官方源码保持不变。

实际浏览器截图：[对话输入框上方的天气条](./assets/official-mods/token-weather.png)、[同一对话内的正文回放](./assets/official-mods/replay-theater.png)、[Blast Radius 限制](./assets/official-mods/blast-radius-limitations.png)。前两张已替换此前仅展示独立页面的截图。

## 适配内容与边界

- `$.session.usage()` 从当前会话对应 Task 读取 `context_input_tokens`，窗口使用当前模型的 `max_context_tokens`；不是将所有调用的输入总数当作当前上下文。没有实际会话和窗口时返回空 context。
- `write_chapter/write_note` 映射为 `Write`，正文查找替换 `edit_chapter/edit_note` 映射为 `Edit`。路径为 `openfic://projects/...` 下的逻辑文档，不是磁盘文件。浏览器用例实际验证章节创建和正文编辑；标题修改、移动、删除和任意主机文件不属于这次映射范围。
- 通过 JS 桥传输嵌套 Pydantic 参数时生成 JSON DTO；返回执行器时保留未改动参数的原始对象，改写的正文继续走原生工具校验与审批。Mod 不能借映射改变工具身份或重定向逻辑路径。
- LangGraph 的审批/提问中断直接向执行器传播，不转为 JS Error 或失败工具结果；专项测试检查原中断对象原样透传，以及之后仍能正常渲染 Mod。
- `AbovePrompt` 直接映射到当前对话输入框上方，`ui.open` 的 Pane 也在该区域原位展开，不跳转页面。内容根据尺寸自动报告高度；空内容收起，面板最多占 420px 或窗口高度的 45%，保留消息区和输入框。终端布局没有逐像素复制；按钮、面板内快捷键和 Escape 可用。
- 修复 Pane 的 requestId、渲染尺寸、默认空结果、控件刷新和重复命令注册；基础颜色也映射到浏览器样式。
- Blast Radius 的受控事件测试确认：面对风险命令事件，缺少 process 时返回拒绝，未调用后续执行函数。浏览器只通过预览接口派发事件，没有运行 `rm` 或其他 shell 命令。这不代表完整的 Blast Radius 功能兼容。

保留官方 Mod 的模块级内存状态；当前实例显示最近活动回合，不提供每个 OpenFic 会话分别隔离的 Claude 终端实例。停用/重启会清除这些内存状态。宿主会在重启时按适配版本重新生成旧 Mod 的宿主包装与插槽，保留官方源码、启用状态和持久化数据；已安装用户重启后端并刷新前端即可使用新布局。

## 端到端路径

官方 Mod 的对话内浏览器用例与三个示例、React/TSX 和项目统计一起执行，Chromium 共 **5 项通过**（约 1.2 分钟）。前端格式、lint、类型检查和 E2E TypeScript 检查通过。上游源码以及实际安装 ZIP 内的配置和执行文件均与记录的 SHA256 一致。

对话内适配修复后的用例从项目的真实对话框发送消息，全程不访问 Token Weather 或 Replay 的插件页面。检查包括：空视图高度为零、天气条位于同一输入框上方且高度不超过 80px、Replay 原位展开/收起、URL 不变、草稿保留、消息区仍可见，以及宿主的高度上限。插件、工具基础和 orchestrator 专项 **62 passed**；启动、应用入口、认证与访问日志 **28 passed**。旧版宿主包装的迁移测试检查了源码、持久化数据和启用状态保留。生产前端与正式 wheel 构建通过，wheel 包含最新内嵌前端和 Mod 适配实现。

此前 SDK/官方 Mod 适配的后端全量回归为 **2295 passed、19 skipped**（300.05 秒）；本次 UI 位置与自动迁移修复使用上述专项回归。Ruff、ty 均通过。跳过项来自测试环境条件，不计为通过。

测试使用真实应用、数据库、插件宿主、RPC、iframe 和原生 Agent 工具；模型提供商使用本地 OpenAI 协议仿真，以稳定产生章节创建与编辑。没有使用真实付费模型或启动 Claude Code 客户端。

官方 Mod 用例执行：登录 → 管理 UI 安装三个原包 → 启用 → 检查限制 → 打开项目与章节 → 在真实对话框发送消息 → Agent 实际创建章节并修改已有正文 → Task 记录与输入框上方均显示 `16k / 32k、50%` → 同一对话内两步回放、关闭和高度恢复 → 不兼容边界 → 停用与卸载。用例结束删除临时项目、模型、提供商并恢复设置。

测试代码：

- `backend/tests/plugins/test_official_mods.py`：原始源码校验、安装、真实 Task 用量、原生类型参数、事件往返、回放、路径/工具身份边界、Bash 不兼容行为。
- `frontend/e2e/official-mods.spec.ts`：上述完整浏览器路径，输出管理页、天气、回放和限制页面截图。
- `backend/tests/plugins/fixtures/claude-playground/provenance.json`：上游 commit 与所有配置/执行文件的 SHA256。

## 复现

启动隔离后端与静态预览的方式见 [示例插件验证](./plugin-examples.md#打包与本地验证)。生产前端无需为了安装这些 Mod 重新构建。然后：

```bash
git clone https://github.com/anthropics/claude-code-playground.git /tmp/claude-code-playground
git -C /tmp/claude-code-playground checkout 569c5283d9a0a7ee7938df85bb32e4f48cbb8c86

cd frontend
OPENFIC_OFFICIAL_MODS_DIR=/tmp/claude-code-playground/claude-code/mods \
OPENFIC_E2E_BASE_URL=http://127.0.0.1:9012 \
OPENFIC_E2E_BACKEND=http://127.0.0.1:8011 \
OPENFIC_E2E_PASSWORD=test-password \
  pnpm exec playwright test e2e/official-mods.spec.ts e2e/plugin-sdk.spec.ts e2e/plugins.spec.ts
```

省略 `OPENFIC_OFFICIAL_MODS_DIR` 时使用仓库内同一版本的原始运行文件 fixture，不需要网络。使用系统 Chromium 时可另设 `OPENFIC_E2E_CHROMIUM_PATH`。安装原包的 ZIP 会保存在 `/tmp/openfic-official-<name>.zip`。

```bash
cd backend
uv run pytest tests/plugins/test_official_mods.py -q
```
