# Human–AI Collaboration（实验性）

在「设置 → 高级」开启 **Human-AI Collaboration（实验性）**。默认为关闭。
关闭时继续使用现有的章节自动保存与 Agent 运行时编辑锁；角色、笔记、世界书等编辑器继续使用原有行为。

开启后，章节正文使用 Tiptap Collaboration、Yjs 与 Hocuspocus：用户和 Agent 的修改合并到同一份 `Y.XmlFragment("default")`，不会通过 `setContent()` 重载整篇章节。标题仍通过现有元数据 API 保存。

## 安装与运行

源码开发需要 Node.js 22+、pnpm 和现有 Python 环境：

```sh
cd collaboration
pnpm install --frozen-lockfile
pnpm build
cd ../frontend
pnpm install --frozen-lockfile
```

照常启动 OpenFic。后端首次开启实验功能时自动启动 Hocuspocus 子进程，监听随机的本机回环端口；浏览器通过已认证的 `/api/v1/collaboration/chapters/{id}/{epoch}` WebSocket 代理连接，无须暴露额外端口。反向代理应允许这个路径的 WebSocket Upgrade。

Docker 镜像包含 Node 和打包后的服务；Python wheel 构建过程打包服务，运行 wheel 时仍需可用的 Node。桌面端复用 Electron 的 Node 运行时。可用 `OPENFIC_NODE_BINARY` 指定 Node/Electron 可执行文件。

当前实验功能要求单个后端进程拥有应用数据库；不要以多个 Uvicorn/Gunicorn worker 或多个副本同时开启此功能。跨进程共享文档需要额外的 Hocuspocus 分布式协调。

## 一致性与持久化

- `chapter_collaboration` 保存文档 epoch、单调递增版本及 **Yjs 二进制状态**；文本快照与该状态在同一个业务数据库事务内保存。原有章节查询、统计、搜索、索引与摘要读取文本快照。
- 浏览器使用 `y-indexeddb` 保留断线期间的 CRDT 更新，重连后合并。首次完成同步前正文不可编辑；完成一次同步后，断线编辑保存在本地并显示重连状态。
- Agent 的 `edit_chapter(old_content, new_content)` 接口不变。协同模式使用最新正文上的精确、唯一匹配（`replace_all` 可替换所有精确匹配）。目标已改变或含糊时返回冲突，Agent 应重新读取章节；不会模糊替换用户刚改写的目标。
- Agent 修改先在共享文档的副本上准备，在同一 SQL 事务内保存二进制状态、文本及 Revision/Commit，提交后才广播 Yjs 更新。用户同时产生的更新随后合并，避免未提交的 Agent 修改先暴露给编辑器。
- 协同模式拒绝传统 REST 正文覆盖，但允许标题更新。传统编辑器提交 `expected_updated_at`，防止切换模式或后台刷新时的旧全文覆盖。
- 关闭功能前暂停连接并保存在线文档。关闭期间若正文被传统方式修改，旧 epoch 作废；重新开启时不会把旧 IndexedDB 历史混入新正文。
- 如果已有未保存的传统草稿，协同编辑器提示先关闭功能并处理草稿，不会自动用它替换共享文档。切换模式需等待 Agent 会话结束。

## 撤销与回滚

用户撤销由 Yjs UndoManager 管理，保留其他编辑者和 Agent 的修改。Agent Revision 回滚在最新共享文档上生成反向局部编辑，保留可独立定位的用户改动；目标消失或不唯一时拒绝回滚，避免恢复整篇旧快照覆盖用户内容。

章节创建/删除的 Revision 结构回滚暂不在协同模式执行，需关闭实验功能后使用原有回滚流程。CRDT 保证结构收敛，不代替语义冲突审查。

## 验证

```sh
cd collaboration
pnpm test
cd ../backend
uv run pytest tests/api/test_collaboration.py tests/api/test_collaboration_worker.py tests/agent_runtime/tools/test_chapter_tools.py
cd ../frontend
pnpm type-check
# 启动后端 :8000 和前端 :9000 后
pnpm exec playwright test chapter-collaboration.spec.ts chapter-whitespace.spec.ts
```

真实 Node/SQL 集成测试不调用 LLM：覆盖 Agent 工具写入、Revision 快照、二进制恢复及保留用户尾部修改的反向编辑。浏览器测试覆盖双编辑器同步、光标、局部撤销、Agent 运行期间继续输入和刷新恢复。
