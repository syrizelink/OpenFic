# 后台 Subagent

`dispatch_subagent` 和 `notify_subagent` 新增可选的 `background` 参数，默认 `false`，保留原有同步等待行为。

## 调用方式

```json
{
  "agent_type": "explore",
  "description": "检查人物时间线",
  "prompt": "检查指定章节的人物时间线，返回矛盾及章节位置，不修改内容。",
  "background": true
}
```

后台派发立即返回 `dispatch_id`、`request_id`、`agent_number`、`background` 和初始状态。主代理可以继续调用工具处理其他独立工作。

继续同一子会话时，调用 `notify_subagent`：

```json
{
  "dispatch_id": "上次返回的 dispatch_id",
  "prompt": "继续检查下一组章节。",
  "background": true
}
```

同一子会话内的请求仍顺序执行，不会同时修改同一个子会话的消息历史。每个请求拥有独立的 `request_id`，结果不会取用其他轮次的最后一条回复。

通知以父会话、当前修订和工具调用 ID 标识一次操作。同一调用重放时返回原 `request_id`，不会重复创建请求或用户消息；改变目标、正文或执行方式的重放会明确报错。不同工具调用或不同修订中的同文通知仍是独立请求。请求、执行方式和对应用户消息在同一数据库事务中保存，因此提交前中断可整体重试，提交后中断则复用原记录。迁移 `1032` 为旧请求保留空身份，并为新请求添加唯一约束。

每个任务树最多有 **10 个**待运行、运行中或等待用户审批的子代理，跨模型轮次、跨工具批次共同计数。数据库锁串行化名额检查与请求接纳，避免并发超额；运行注册表中尚未完成清理的任务也计入占用。完成、失败、取消或回收并退出运行后释放名额；历史已结束会话不长期占用名额。

通知已运行或排队的同一子代理不需要额外名额；通知空闲子代理则须重新取得名额。达到上限时工具报错，不创建被拒绝的子代理、通知请求或消息。等待或取消已有工作后可以重新派发。原有单批派发数量限制仍保留。

需要结果才能继续时，可以调用 `wait_subagents`：

```json
{
  "dispatch_ids": ["dispatch_id_1", "dispatch_id_2"],
  "timeout_seconds": 30
}
```

该工具绑定调用开始时各子会话的最新请求，任一请求完成、失败、取消或等待用户审批时返回。`results` 中包含 `request_id`、`status` 和结果或错误。`timed_out: true` 表示本次等待到期，后台任务继续执行。`timeout_seconds` 范围为 0–300 秒，默认 30 秒；0 表示立即查看。

## 调度与结果回传

- 子任务继续由 `AgentRunRegistry` 注册和管理。后台模式省略派发工具中的结果等待，不另外创建脱离会话的 worker。
- `AgentChildRunRequest.background` 持久化执行方式；`result_delivered` 记录自动投递状态。迁移版本为 `1030`，随应用启动执行现有数据库迁移流程。
- 主代理在每次模型调用前收集结果，将它们作为明确标注来源的子代理报告加入上下文。报告与投递记录在同一数据库事务内保存，模型调用失败时可以重新读取。
- 主代理准备结束当前轮次时，如果仍有未投递的后台请求，就释放数据库会话并等待。结果到达后自动继续推理，避免遗漏结果；等待期间用户注入的新消息也可唤醒主代理。模型迭代上限仍生效。
- 子代理审批沿用现有子会话审批和恢复流程。`wait_subagents` 会报告 `waiting_user`，自动等待则保持当前父任务存活，直到用户处理审批。
- 停止父会话继续使用现有会话树取消逻辑；回收子会话或回滚所属修订后，不再自动投递这些请求。服务重启继续沿用现有策略，将未完成任务标为取消，不保证跨进程持续执行。
- 前端沿用子代理实时状态面板，后台派发、通知卡片显示对应标识。内部结果消息对用户隐藏，由主代理汇总后回复。

并行任务应操作相互独立的章节、设定或笔记。主代理应等待所需结果后再汇总结论，不要轮询、重复执行子任务，或让多个代理同时修改同一内容。

## 实现参考

- [KiloCode task 工具](https://github.com/Kilo-Org/kilocode/blob/main/packages/opencode/src/tool/task.ts)：可选 `background`、立即返回任务标识、完成后向父会话注入结果。
- [Codex spawn](https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/handlers/multi_agents/spawn.rs) 与 [wait](https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/handlers/multi_agents/wait.rs)：分离启动和等待，独立任务标识，等待任一结果与有界超时。

OpenFic 将这些机制接入现有 LangGraph 轮次、持久化请求队列、审批和取消流程。

## 测试

参见[不需要 API key 的端到端测试](background-subagents-e2e.md)，包含真实前后端、浏览器审批与回滚、并发取消竞态、离线恢复和服务进程重启。

可靠性专项可通过 `frontend` 目录中的 `pnpm test:e2e:reliability` 运行：覆盖同调用重放、跨轮次占满并发名额后拒绝超额任务、名额释放后接纳替补、空闲通知的名额检查，以及看板提醒查询故障和恢复。报告位于 `frontend/playwright-report/reliability/index.html`。后端专项是 `tests/agent_runtime/test_subagent_reliability.py`、看板上下文故障测试和迁移 `1032` 的升降级测试。
