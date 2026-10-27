import { randomUUID } from "node:crypto";

import { expect, type APIRequestContext, type Page } from "@playwright/test";

import { openProject, sendMessage } from "./helpers";

export interface Step {
  until_results?: number;
  text?: string;
  partial_text?: string;
  gate?: string;
  http_status?: number;
  error?: string;
  malformed_stream?: boolean;
  tools?: { id: string; name: string; args: Record<string, unknown> }[];
}

export interface Script {
  parent: Step[];
  children: Record<string, Step[]>;
}

export interface State {
  checkpoint_errors: string[];
  calls: {
    actor: string;
    step: number;
    gate?: string;
    cancelled?: boolean;
    unexpected?: boolean | string;
    http_status?: number;
    messages: { role: string; content?: string; tool_call_id?: string }[];
  }[];
  children: {
    id: string;
    dispatch_id: string;
    child_thread_id: string;
    status: string;
    is_active: boolean;
    runtime_running: boolean;
    metadata_json?: { agent_number?: string };
    pending_approval_json: Record<string, unknown> | null;
  }[];
  requests: {
    id: string;
    child_run_id: string;
    seq: number;
    status: string;
    background: boolean;
    result_delivered: boolean;
    content: string;
    assistant_content: string | null;
    error: string | null;
  }[];
  messages: {
    id: string;
    role: string;
    message_type: string;
    display_channel: string;
    content: string;
    tool_name?: string;
    tool_call_id?: string;
    message_metadata: string;
  }[];
  task: {
    id: string;
    title: string;
    is_running: boolean;
    current_revision_id: string | null;
  } | null;
  notes: { id: string; title: string; content: string }[];
  revisions: { id: string; status: string }[];
  parent_running: boolean;
}

export const control = "/api/v1/__e2e__";
export const call = (id: string, name: string, args: Record<string, unknown> = {}) => ({
  id,
  name,
  args,
});
export const dispatch = (label = "one", background: boolean | "omit" = true) =>
  call(label, "dispatch_subagent", {
    agent_type: "explore",
    description: `后台任务-${label}`,
    prompt: `E2E_SCENARIO:$SCENARIO E2E_CHILD:${label} 检查人物时间线，返回独立结论。`,
    ...(background === "omit" ? {} : { background }),
  });

export async function checked<T>(
  request: APIRequestContext,
  method: string,
  url: string,
  data?: unknown,
): Promise<T> {
  const response = await request.fetch(url, { method, data });
  expect(response.ok(), `${method} ${url}: ${await response.text()}`).toBeTruthy();
  return response.json() as Promise<T>;
}

export async function seed(request: APIRequestContext) {
  const port = Number(process.env.OPENFIC_E2E_BACKEND_PORT ?? 19001);
  const providerResponse = await request.post("/api/v1/model-providers", {
    form: {
      provider_type: "openai-compatible",
      name: "Local E2E only",
      api_key: "e2e-not-a-secret",
      url: `http://127.0.0.1:${port}${control}/model/v1`,
    },
  });
  expect(providerResponse.ok(), await providerResponse.text()).toBeTruthy();
  const provider = (await providerResponse.json()) as { id: string; url: string };
  expect(provider.url).toContain(`127.0.0.1:${port}`);
  const model = await checked<{ id: string }>(request, "POST", "/api/v1/models", {
    name: `E2E scripted model ${randomUUID()}`,
    model_id: "e2e-scripted",
    provider_id: provider.id,
    context_length: 0,
  });
  await checked(request, "PUT", "/api/v1/settings", {
    default_model: model.id,
    light_model: model.id,
    telemetry_enabled: false,
    agent_bypass_tool_approval: false,
    summary_auto_generate_chapter: false,
    summary_auto_generate_long_term: false,
  });
  await checked(request, "PUT", "/api/v1/agent-definitions/build", {
    model_id: model.id,
    enabled_tool_categories: ["orchestration", "interaction", "note_read", "note_write"],
    delegatable_agents: ["explore"],
  });
  await checked(request, "PUT", "/api/v1/agent-definitions/explore", {
    model_id: model.id,
    enabled_tool_categories: ["note_read", "note_write"],
  });
  return model.id;
}

export class Scenario {
  sessionId = "";
  readonly page: Page;
  readonly id: string;
  readonly projectId: string;

  constructor(page: Page, id: string, projectId: string) {
    this.page = page;
    this.id = id;
    this.projectId = projectId;
  }

  async start() {
    await openProject(this.page, `/projects/${this.projectId}`);
    const created = this.page.waitForResponse(
      (response) =>
        response.request().method() === "POST" && /\/agent\/sessions$/.test(response.url()),
    );
    await sendMessage(this.page, `E2E_SCENARIO:${this.id} 请执行预定任务。`);
    const response = await created;
    expect(response.ok(), await response.text()).toBeTruthy();
    this.sessionId = ((await response.json()) as { session_id: string }).session_id;
  }

  state() {
    return checked<State>(
      this.page.request,
      "GET",
      `${control}/scenarios/${this.id}/state?session_id=${this.sessionId}`,
    );
  }

  async until(predicate: (state: State) => boolean, message = "scenario state", timeout = 20_000) {
    await expect.poll(async () => predicate(await this.state()), { message, timeout }).toBe(true);
    return this.state();
  }

  async release(gate = "hold") {
    await checked(this.page.request, "POST", `${control}/scenarios/${this.id}/release/${gate}`);
  }

  async finish(text = "E2E_DONE") {
    await this.until(
      (state) => !state.parent_running && state.task?.is_running === false,
      "parent and task finish",
    );
    await expect(
      this.page.locator(".agent-message-scroll-content").getByText(text).first(),
    ).toBeVisible();
    const state = await this.state();
    expect(
      state.calls.filter((item) => item.unexpected),
      "unexpected model requests",
    ).toEqual([]);
    expect(state.children.every((child) => !child.runtime_running)).toBe(true);
    return state;
  }

  async cancel() {
    if (!this.sessionId) return;
    await this.page.request.post(`/api/v1/agent/sessions/${this.sessionId}/cancel`, { data: {} });
    await this.until(
      (state) => !state.parent_running && state.children.every((child) => !child.runtime_running),
      "all runtime tasks stop",
    );
  }

  async reopen() {
    const state = await this.state();
    await expect(this.page.getByText(state.task!.title, { exact: true }).first()).toBeVisible();
    await this.page.getByText(state.task!.title, { exact: true }).first().click();
    await expect(this.page.locator(".agent-message-scroll-content")).toBeVisible();
    await expect(
      this.page.locator(".ai-sidebar-input-body[data-mode='composer'] [contenteditable='true']"),
    ).toBeVisible();
  }
}

export async function scenario(page: Page, script: Script): Promise<Scenario> {
  const id = randomUUID();
  await checked(
    page.request,
    "POST",
    `${control}/scenarios/${id}`,
    JSON.parse(JSON.stringify(script).replaceAll("$SCENARIO", id)),
  );
  const response = await page.request.post("/api/v1/projects", {
    form: { title: `后台测试-${id.slice(0, 8)}` },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  const project = (await response.json()) as { id: string };
  return new Scenario(page, id, project.id);
}

export function deliveries(state: State) {
  return state.messages.filter((message) => message.message_type === "subagent_result");
}

export function toolResult(state: State, id: string) {
  const message = state.messages.find((item) => item.role === "tool" && item.tool_call_id === id);
  expect(message, `persisted tool result ${id}`).toBeTruthy();
  return JSON.parse(message!.content) as Record<string, unknown>;
}
