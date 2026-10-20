import { Text } from "@radix-ui/themes";
import { useQuery } from "@tanstack/react-query";
import { type ComponentType, type ReactElement, type ReactNode } from "react";

import { CircularProgress } from "@/components/circular-progress";
import { InfoTooltip } from "@/components/info-tooltip";
import { ModelIdSelect } from "@/components/model-id-select";
import { ProjectGridSelector } from "@/components/project-grid-selector";
import { ProjectSelectField } from "@/components/project-select-field";
import { LabeledSelect, SearchableSelect } from "@/components/select";
import { Spinner } from "@/components/spinner";
import { StepperNumberInput } from "@/components/stepper-number-input";
import { UnitTextField } from "@/components/unit-text-field";
import { apiClient, resolveBackendUrl } from "@/lib/api-client";
import type { Project } from "@/lib/project.types";

import { pluginError } from "./api";
import { DeclarativeFloatingPanel } from "./declarative-floating-panel";
import { DeclarativeImage } from "./declarative-image";
import type { UIProps, UIValue } from "./declarative-schema";

interface ProjectProps {
  name: string;
  props: UIProps;
  forwarded: Record<string, unknown>;
  children: ReactNode;
  pluginId: string;
  change: (value: UIValue, kind?: string) => void;
}
type Row = Record<string, unknown>;
function str(value: unknown, fallback = "") {
  return typeof value === "string" ? value : fallback;
}
async function resource(
  pluginId: string,
  path: string,
  query: Record<string, string | number> = {},
) {
  const response = await apiClient.post<{ result: unknown }>("/plugins/" + pluginId + "/rpc", {
    method: "sdk.api.request",
    params: { method: "GET", path, query },
  });
  return response.data.result;
}
function ModelControl({ props: p, pluginId, change }: ProjectProps) {
  const kind = str(p.taskType, "llm");
  const query = useQuery({
    queryKey: ["plugin-component-data", pluginId, "models", kind],
    queryFn: () => resource(pluginId, "/models", { task_type: kind }),
  });
  const rows = Array.isArray(query.data) ? (query.data as Row[]) : [];
  const models = rows
    .filter((row) => row.task_type === kind)
    .map((row) => ({
      id: str(row.model_id),
      value: str(row.id),
      name: str(row.name),
      contextWindow: typeof row.context_length === "number" ? row.context_length : null,
    }));
  return (
    <ModelIdSelect
      value={str(p.value)}
      onChange={(value) => change(value, "select")}
      models={models}
      isLoading={query.isLoading}
      error={query.error ? pluginError(query.error) : undefined}
      placeholder={str(p.placeholder, str(p.label))}
      disabled={Boolean(p.disabled)}
      taskType={kind as "llm" | "embedding" | "rerank"}
      editable={p.editable !== false}
      allowCustomValue={Boolean(p.allowCustomValue)}
      compact={Boolean(p.compact)}
      compactTrigger={Boolean(p.compactTrigger)}
      hideTriggerChevron={Boolean(p.hideTriggerChevron)}
      emptyOptionLabel={typeof p.emptyOptionLabel === "string" ? p.emptyOptionLabel : undefined}
      triggerClassName={str(p.triggerClassName)}
      contentClassName={str(p.contentClassName)}
    />
  );
}
async function projectsFor(pluginId: string) {
  const rows: Row[] = [];
  for (let page = 1; ; page++) {
    const data = (await resource(pluginId, "/projects", { page, page_size: 100 })) as {
      items: Row[];
      total: number;
    };
    rows.push(...data.items);
    if (data.items.length < 100 || rows.length >= data.total) return rows;
  }
}
function ProjectControl(input: ProjectProps) {
  const { props: p, pluginId, change } = input;
  const query = useQuery({
    queryKey: ["plugin-component-data", pluginId, "projects"],
    queryFn: () => projectsFor(pluginId),
  });
  const raw = query.data ?? [];
  const projects: Project[] = (Array.isArray(raw) ? (raw as Row[]) : []).map((row) => ({
    id: str(row.id),
    title: str(row.title),
    description: str(row.description),
    wordCount: Number(row.word_count ?? 0),
    chapterCount: Number(row.chapter_count ?? 0),
    coverUrl: typeof row.cover_url === "string" ? resolveBackendUrl(row.cover_url) : null,
    createdAt: str(row.created_at),
    updatedAt: str(row.updated_at),
  }));
  if (query.error) return <Text role="alert">{pluginError(query.error)}</Text>;
  const Component = input.name === "ProjectGridSelector" ? ProjectGridSelector : ProjectSelectField;
  return (
    <Component
      projects={projects}
      value={str(p.value)}
      disabled={Boolean(p.disabled) || query.isLoading}
      showNoneOption={p.showNoneOption !== false}
      placeholder={str(p.placeholder)}
      label={str(p.label)}
      onChange={(value) => change(value, "select")}
    />
  );
}
/** Registry entries are actual project components, never copies of their presentation. */
const components: Record<string, ComponentType<Record<string, unknown>>> = {
  Spinner,
  CircularProgress,
  UnitTextField,
  StepperNumberInput,
  LabeledSelect,
  SearchableSelect,
  InfoTooltip,
} as unknown as Record<string, ComponentType<Record<string, unknown>>>;
export function ProjectComponent(input: ProjectProps) {
  const { name, props: p, forwarded, children, change } = input;
  if (name === "Image")
    return (
      <DeclarativeImage
        {...input.forwarded}
        pluginId={input.pluginId}
        asset={str(p.asset)}
        alt={str(p.alt)}
        width={typeof p.width === "number" ? p.width : undefined}
        height={typeof p.height === "number" ? p.height : undefined}
      />
    );
  if (name === "FloatingPanel")
    return (
      <DeclarativeFloatingPanel
        forwarded={input.forwarded}
        position={p.position}
        width={typeof p.width === "number" ? p.width : undefined}
        dragLabel={str(p.dragLabel, "Move panel")}
        onPositionChange={(value) => input.change(value)}
      >
        {input.children}
      </DeclarativeFloatingPanel>
    );
  if (name === "ModelIdSelect") return <ModelControl {...input} />;
  if (name === "ProjectSelectField" || name === "ProjectGridSelector")
    return <ProjectControl {...input} />;
  const Component = components[name];
  const props: Record<string, unknown> = { ...forwarded };
  if (name === "LabeledSelect" || name === "SearchableSelect") {
    props.options = p.options ?? [];
    props.label = typeof p.label === "string" ? p.label : undefined;
    props.placeholder = str(p.placeholder, str(p.label));
    props.value = str(p.value);
    props.onChange = (value: string) => change(value, "select");
    props.triggerAriaLabel = str(p.label, "Select");
    delete props.className;
    delete props.style;
  }
  if (name === "StepperNumberInput") {
    props.value = p.value ?? 0;
    props.increaseAriaLabel = str(p.increaseAriaLabel, "Increase");
    props.decreaseAriaLabel = str(p.decreaseAriaLabel, "Decrease");
  }
  if (name === "CircularProgress") props.value = typeof p.value === "number" ? p.value : 0;
  if (name === "InfoTooltip") props.children = children as ReactElement;
  return <Component {...props}>{name === "InfoTooltip" ? children : undefined}</Component>;
}
