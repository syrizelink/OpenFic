/// <reference types="node" />

import assert from "node:assert/strict";
import test from "node:test";

import type { ModelProvider } from "@/lib/model.types";

import {
  hasSelectableModelProvider,
  isSelectableModelProviderForTask,
} from "./provider-utils";

function createProvider(overrides: Partial<ModelProvider> = {}): ModelProvider {
  return {
    id: "provider-1",
    name: "",
    url: "http://localhost:11434",
    providerType: "builtin",
    supportedTaskTypes: [],
    iconPath: null,
    isBuiltin: true,
    catalogMatch: null,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

test("isSelectableModelProviderForTask returns false for builtin provider even when it declares supported tasks", () => {
  const provider = createProvider({
    supportedTaskTypes: ["embedding", "rerank"],
  });

  assert.equal(isSelectableModelProviderForTask(provider, "llm"), false);
  assert.equal(isSelectableModelProviderForTask(provider, "embedding"), false);
});

test("isSelectableModelProviderForTask keeps openai-compatible providers selectable", () => {
  const provider = createProvider({
    providerType: "openai-compatible",
    isBuiltin: false,
  });

  assert.equal(isSelectableModelProviderForTask(provider, "llm"), true);
});

test("hasSelectableModelProvider returns false when only builtin local provider exists", () => {
  const providers = [
    createProvider({
      supportedTaskTypes: ["embedding", "rerank"],
    }),
  ];

  assert.equal(hasSelectableModelProvider(providers), false);
});

test("hasSelectableModelProvider returns true when at least one provider supports a task", () => {
  const providers = [
    createProvider(),
    createProvider({
      id: "provider-2",
      providerType: "ollama",
      isBuiltin: false,
      supportedTaskTypes: ["llm"],
    }),
  ];

  assert.equal(hasSelectableModelProvider(providers), true);
});
