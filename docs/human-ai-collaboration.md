# Human–AI Collaboration（实验性）

在「设置 → 高级」开启 **Human-AI Collaboration（实验性）**。默认为关闭。
关闭时继续使用现有的章节自动保存与 Agent 运行时编辑锁；角色、笔记、世界书等编辑器继续使用原有行为。

开启后，章节正文使用 Tiptap Collaboration、Yjs 与 Python 的 pycrdt：用户和 Agent 的修改合并到同一份 `Y.XmlFragment("default")`，不会通过 `setContent()` 重载整篇章节。标题仍通过现有元数据 API 保存。

## 安装与运行

协同同步直接运行在现有 FastAPI 进程中。后端不需要 Node.js，不启动子进程，也不监听额外端口。pycrdt 是普通 Python 依赖，随现有依赖一起安装。

```sh
cd backend
uv sync
cd ../frontend
pnpm install --frozen-lockfile
pnpm dev
```

照常启动 OpenFic。浏览器通过现有后端的 `/api/v1/collaboration/chapters/{id}/{epoch}` WebSocket 连接共享章节。反向代理应允许这个路径的 WebSocket Upgrade。前端构建仍使用项目原有的 Node/pnpm 工具链；后端运行没有额外的 JavaScript 服务。

Docker、Python wheel 和桌面端均使用同一套 Python 同步逻辑，无需打包或配置额外运行时。先前已保存的 Yjs 二进制文档可以直接加载，文档表和 epoch 格式保持兼容。

当前实验功能要求单个后端进程拥有应用数据库；不要以多个 Uvicorn/Gunicorn worker 或多个副本同时开启此功能。跨进程共享文档需要额外的跨进程状态协调。

## 一致性与持久化

- `chapter_collaboration` 保存文档 epoch、单调递增版本及 **Yjs 二进制状态**；文本快照与该状态在同一个业务数据库事务内保存。原有章节查询、统计、搜索、索引与摘要读取文本快照。
- 浏览器使用 `y-indexeddb` 保留断线期间的 CRDT 更新，重连后合并。首次完成同步前正文不可编辑；完成一次同步后，断线编辑保存在本地并显示重连状态。
- Agent 的 `edit_chapter(old_content, new_content)` 接口不变。协同模式使用最新正文上的精确、唯一匹配（`replace_all` 可替换所有精确匹配）。目标已改变或含糊时返回冲突，Agent 应重新读取章节；不会模糊替换用户刚改写的目标。
- Agent 修改先在共享文档的副本上准备，在同一 SQL 事务内保存二进制状态、文本及 Revision/Commit，提交后才广播 Yjs 更新。浏览器更新同样先验证并持久化，再广播；同章写入通过现有后端中的文档锁串行提交，Yjs 合并客户端的并发操作。
- 协同模式拒绝传统 REST 正文覆盖，但允许标题更新。传统编辑器提交 `expected_updated_at`，防止切换模式或后台刷新时的旧全文覆盖。
- 所有接收的更新都在确认同步前持久化；关闭功能时停止接收更新并断开协同连接。关闭期间若正文被传统方式修改，旧 epoch 作废；重新开启时不会把旧 IndexedDB 历史混入新正文。
- 如果已有未保存的传统草稿，协同编辑器提示先关闭功能并处理草稿，不会自动用它替换共享文档。切换模式需等待 Agent 会话结束。

## 撤销与回滚

用户撤销由 Yjs UndoManager 管理，保留其他编辑者和 Agent 的修改。Agent Revision 回滚在最新共享文档上生成反向局部编辑，保留可独立定位的用户改动；目标消失或不唯一时拒绝回滚，避免恢复整篇旧快照覆盖用户内容。

章节创建/删除的 Revision 结构回滚暂不在协同模式执行，需关闭实验功能后使用原有回滚流程。CRDT 保证结构收敛，不代替语义冲突审查。

## 验证

```sh
cd backend
uv run pytest tests/api/test_collaboration.py tests/api/test_collaboration_document.py tests/api/test_collaboration_in_process.py tests/agent_runtime/tools/test_chapter_tools.py
cd ../frontend
pnpm type-check
# 启动现有后端与前端后
pnpm exec playwright test chapter-collaboration.spec.ts chapter-whitespace.spec.ts
```

真实 Python/SQL 集成测试不调用 LLM：覆盖 Agent 工具写入、Revision 快照、二进制恢复及保留用户尾部修改的反向编辑。测试禁止协同逻辑创建子进程。浏览器测试覆盖双编辑器同步、光标、局部撤销、Agent 运行期间继续输入和刷新恢复。
