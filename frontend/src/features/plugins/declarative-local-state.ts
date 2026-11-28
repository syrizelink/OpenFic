import { useEffect, useMemo, useState } from "react";

import type {
  UILocalDefinition,
  UILocalOperation,
  UILocalValue,
  UIValue,
} from "./declarative-schema";

function validJSON(value: unknown, depth = 0): value is UILocalValue {
  if (value === null || typeof value === "boolean") return true;
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value === "string") return value.length <= 65536;
  if (depth >= 16 || typeof value !== "object") return false;
  if (Array.isArray(value))
    return value.length <= 200 && value.every((item) => validJSON(item, depth + 1));
  if (Object.getPrototypeOf(value) !== Object.prototype && Object.getPrototypeOf(value) !== null)
    return false;
  const entries = Object.entries(value);
  return entries.length <= 128 && entries.every(([, item]) => validJSON(item, depth + 1));
}

function validValue(value: unknown, initial: UILocalValue): value is UILocalValue {
  if (value === null) return true;
  if (initial === null) {
    if (!validJSON(value)) return false;
    return JSON.stringify(value).length <= 65536;
  }
  if (typeof initial === "number") return typeof value === "number" && Number.isFinite(value);
  if (typeof initial === "object") {
    if (
      !value ||
      typeof value !== "object" ||
      Array.isArray(value) !== Array.isArray(initial) ||
      !validJSON(value)
    )
      return false;
    try {
      return JSON.stringify(value).length <= 65536;
    } catch {
      return false;
    }
  }
  return typeof value === typeof initial && (typeof value !== "string" || value.length <= 65536);
}

export function useDeclarativeLocalState(
  pluginId: string,
  viewId: string,
  definitions: Record<string, UILocalDefinition>,
  actions: Record<string, UILocalOperation[]>,
) {
  const scope = JSON.stringify([pluginId, viewId]);
  const definitionKey = JSON.stringify(definitions);
  const declared = useMemo(
    () => JSON.parse(definitionKey) as Record<string, UILocalDefinition>,
    [definitionKey],
  );
  const initial = useMemo(() => {
    const result: Record<string, UILocalValue> = {};
    for (const [name, definition] of Object.entries(declared)) {
      result[name] = definition.initial;
      if (!definition.persist) continue;
      try {
        const raw = localStorage.getItem(
          `openfic:plugin-state:${JSON.stringify([pluginId, viewId, name])}`,
        );
        if (raw !== null) {
          const saved: unknown = JSON.parse(raw);
          if (validValue(saved, definition.initial)) result[name] = saved;
        }
      } catch {
        // Ignore unavailable storage or malformed saved values.
      }
    }
    return result;
  }, [pluginId, viewId, declared]);
  const [current, setCurrent] = useState<{ scope: string; values: Record<string, UILocalValue> }>({
    scope,
    values: {},
  });
  const values: Record<string, UILocalValue> = {};
  for (const [name, definition] of Object.entries(declared)) {
    const saved =
      current.scope === scope && Object.hasOwn(current.values, name)
        ? current.values[name]
        : initial[name];
    values[name] = validValue(saved, definition.initial) ? saved : definition.initial;
  }
  useEffect(() => {
    setCurrent((previous) => {
      const next: Record<string, UILocalValue> = {};
      for (const [name, definition] of Object.entries(declared)) {
        const saved =
          previous.scope === scope && Object.hasOwn(previous.values, name)
            ? previous.values[name]
            : initial[name];
        next[name] = validValue(saved, definition.initial) ? saved : definition.initial;
      }
      if (
        previous.scope === scope &&
        Object.keys(previous.values).length === Object.keys(next).length &&
        Object.keys(next).every(
          (name) =>
            Object.hasOwn(previous.values, name) && Object.is(previous.values[name], next[name]),
        )
      )
        return previous;
      return { scope, values: next };
    });
  }, [scope, declared, initial]);
  useEffect(() => {
    if (current.scope !== scope) return;
    for (const [name, definition] of Object.entries(declared)) {
      if (!definition.persist || !Object.hasOwn(current.values, name)) continue;
      try {
        localStorage.setItem(
          `openfic:plugin-state:${JSON.stringify([pluginId, viewId, name])}`,
          JSON.stringify(current.values[name]),
        );
      } catch {
        // Continue with in-memory state when storage is unavailable.
      }
    }
  }, [current, scope, pluginId, viewId, declared]);

  function apply(name: string, eventValue: UIValue) {
    const operations = actions[name];
    if (!operations) return;
    setCurrent((previous) => {
      const next = { ...initial, ...(previous.scope === scope ? previous.values : {}) };
      for (const operation of operations) {
        const definition = declared[operation.state];
        if (!definition) continue;
        const existing = validValue(next[operation.state], definition.initial)
          ? next[operation.state]
          : definition.initial;
        if (operation.op === "toggle" && typeof existing === "boolean")
          next[operation.state] = !existing;
        else if (operation.op === "cycle" && typeof existing === "number")
          next[operation.state] =
            (((Math.trunc(existing) + 1) % operation.count) + operation.count) % operation.count;
        else if (operation.op === "set") {
          const replacement = "fromEvent" in operation ? eventValue : operation.value;
          if (validValue(replacement, definition.initial)) next[operation.state] = replacement;
        }
      }
      return { scope, values: next };
    });
  }
  return { values, apply };
}
