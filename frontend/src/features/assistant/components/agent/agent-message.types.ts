import type { AgentType } from "@/lib/agent.types";

export interface AgentMessageBlockProps {
  onApplyContent?: (content: string) => void;
}

export const AGENT_NAMES: Record<AgentType, string> = {
  primary: "Primary Agent",
  explorer: "信息探索",
  composer: "任务组织",
  auditor: "计划审查",
  writer: "内容创作",
  actor: "任务执行",
  reviewer: "质量审核",
};
