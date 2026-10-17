# SDK 2.0 示例插件

在侧栏「插件管理」确认可信来源，上传对应 ZIP，然后启用。插件安装在当前连接的后端，前端无需重新构建。

| 安装包 | 作用 |
| --- | --- |
| `examples/plugins/dist/google-drive-sync-1.0.0.zip` | Google Drive 章节双向同步、冲突解决、编辑器入口、Agent 手动同步工具 |
| `examples/plugins/dist/handoff-workflow-1.0.0.zip` | 规划/写作/审稿交接、自定义项目 Graph、结果保存为笔记 |
| `examples/plugins/dist/prompt-elements-1.0.0.zip` | 上下文匹配规则、提示词开关/注入、输入框面板和编辑器操作示例 |

这些插件只使用公共 SDK、Python 标准库及后端已有的 LangGraph/LangChain/regex 依赖；没有直接操作应用 ORM 或导入内部业务模块。

## Google Drive

1. 在 Google Cloud 创建 OAuth 客户端，启用 Drive API。将后端 `/plugin-oauth/callback` 登记为客户端的 Redirect URI。生产环境使用 HTTPS；本机开发可使用 loopback。
2. 在插件配置填写 Client ID、Client Secret。Secret 加密保存。可选设置一个 Google Drive 文件夹 ID。
3. 在独立页面点击「连接 Google Drive」并完成 Google 授权。请求最小 `drive.file` scope，只访问该应用获准访问的文件。已有令牌也可从页面导入，值不会读回前端。
4. 选择项目和同步方向，先预览或立即同步。原生 Agent 可调用 `plugin_google_drive_sync_sync_chapters` 上传已保存章节；写工具沿用应用审批。双向下载和冲突解决在插件 UI 执行。
5. 章节工具栏「云同步」可以先保存当前编辑器，再同步项目。

每章保存成带版本标记、标题和正文的 `.openfic.json` 文件，以项目/章节 ID 关联。相同内容不重复上传，支持分页、令牌刷新和暂时错误重试。两端都改变时不会自动覆盖，页面列出冲突并允许显式选择本地或云端版本；下载也走业务更新 API。远程 ETag 可用时进行条件更新。

不传播删除；拉取/双向模式会导入仅云端存在的章节。云端恢复的章节放入当前项目的第一卷，不同步卷、角色、世界书或整个应用数据库。跨实例自动关联要求同一项目身份；不是根据标题猜测匹配的全库迁移工具。大型同步失败后可重新执行，已完成的映射保留。

真实账户连通性需要你自己的 Google OAuth 配置；仓库的自动化测试使用 OAuth/Drive 协议仿真，不代表已替你授权过真实账号。

## Handoff

独立页面提供两种运行：

- 「演示交接」不调用模型，展示确定性的 planner → writer → reviewer 流程。
- 「运行工作流」调用选中的模型。模型通过 `handoff_to_*` Tool 请求转移，节点返回 LangGraph `Command(goto=...)`，审稿可交回写作。步骤上限避免无穷交接。

结果可导出或通过 SDK 保存为项目笔记。点击「为此项目启用 Handoff」后，后续原生 Agent 回合改用这个 Graph；点击「恢复内置工作流」取消选择。独立运行和替换原生 Graph 都经过测试。

示例的内部 handoff Tool 只控制交接，不修改业务数据。它使用真实 Tool 事件，使会话中每条工具调用都有配对的结果。应用级其他插件工具仍由内置 Agent 工具集提供；自定义 Graph 要使用哪些业务工具，由 Graph 作者显式设计。

## 动态提示词元素

全局配置和项目覆盖分开保存。元素定义包括 `id/title/enabled/role/position/text`；默认提供人物一致性、战斗细节和梦境三个元素。

规则包括 `conditions`、`match`（all/any）、`priority`、`actions` 与可选 `stop`。条件支持 `last_user`、角色、`context`、`section:<part>`、project、agent 等源，支持包含、相等、前后缀、正则、大小写和否定。动作支持：

- `element.set`：开关元素；`element.text`：替换元素文字。
- `inject`：添加临时消息；`${last_user}`、`${projectId}`、`${sessionId}`、`${agent}` 宏不会执行代码。
- `replace`：按角色替换文字，可使用正则。
- `remove`：移除符合条件的消息。
- `section.hide`：隐藏指定系统片段，例如 `rules`。

默认规则检测最后的用户消息中的战斗词，以及上下文中的梦境。系统元素默认放在系统提示前缀中，保证常见提供商兼容；显式的 `before_last_user/after_last_user` 可以指定更细位置，作者需考虑模型提供商的角色顺序约束。

「预览注入结果」显示命中规则和最终消息；实际 `context.build` 使用同一引擎。规则只改本次模型请求，不覆写数据库历史。正则有时限和长度限制。输入框上方可直接开关元素；章节工具栏还附带读取编辑器、插入保存、撤销的 SDK 操作面板。

## 打包与本地验证

```bash
python examples/plugins/build_package.py examples/plugins/google-drive-sync examples/plugins/dist/google-drive-sync-1.0.0.zip
python examples/plugins/build_package.py examples/plugins/handoff-workflow examples/plugins/dist/handoff-workflow-1.0.0.zip
python examples/plugins/build_package.py examples/plugins/prompt-elements examples/plugins/dist/prompt-elements-1.0.0.zip
```

```bash
cd backend
uv run pytest tests/plugins
```

浏览器测试需要专门的后端实例，不能指向用户数据。测试应用中才有伪 Google/模型服务路由：

```bash
cd backend
OPENFIC_DATA_DIR=/tmp/openfic-sdk-test-data OPENFIC_AUTH_PASSWORD=test-password \
  uv run uvicorn tests.plugins.e2e_app:app --host 127.0.0.1 --port 8011
```

构建前端后运行专门的静态预览服务（已提供运行时后端配置）：

```bash
cd frontend
pnpm build
OPENFIC_E2E_BACKEND=http://127.0.0.1:8011 node e2e/serve-plugin-preview.mjs
```

也可使用开发服务器的对应后端配置。然后：

```bash
cd frontend
OPENFIC_E2E_BASE_URL=http://127.0.0.1:9012 \
OPENFIC_E2E_BACKEND=http://127.0.0.1:8011 \
OPENFIC_E2E_PASSWORD=test-password \
  pnpm exec playwright test e2e/plugin-sdk.spec.ts e2e/plugins.spec.ts
```

测试通过真实管理 UI 安装插件，并清理同名测试插件和临时项目。模型密钥均为测试值，Drive/模型由隔离服务仿真；有意不调用真实外部账户。
