import { describe, expect, it } from "vitest";

import {
  getStreamingFollowSignal,
  resolveFollowBottomStateOnScroll,
} from "./agent-messages-scroll";

describe("getStreamingFollowSignal", () => {
  it("changes when an earlier streaming message receives content", () => {
    const initialMessages = [
      {
        id: "streaming-output",
        type: "agent_output",
        status: "running",
        content: "draft",
        isStreaming: true,
      },
      {
        id: "latest-tool",
        type: "tool",
        status: "running",
        content: "",
        isStreaming: true,
      },
    ];
    const updatedMessages = [
      { ...initialMessages[0], content: "draft content" },
      initialMessages[1],
    ];

    expect(getStreamingFollowSignal(initialMessages)).toBeTypeOf("string");
    expect(getStreamingFollowSignal(updatedMessages)).not.toBe(
      getStreamingFollowSignal(initialMessages),
    );
  });

  it("ignores completed messages", () => {
    const initialMessages = [
      {
        id: "completed-output",
        type: "agent_output",
        status: "completed",
        content: "before",
      },
      {
        id: "streaming-tool",
        type: "tool",
        status: "running",
        content: "",
        isStreaming: true,
      },
    ];
    const updatedMessages = [{ ...initialMessages[0], content: "after" }, initialMessages[1]];

    expect(getStreamingFollowSignal(updatedMessages)).toBe(
      getStreamingFollowSignal(initialMessages),
    );
  });

  it("changes when a streaming tool receives partial arguments", () => {
    const initialMessages = [
      {
        id: "streaming-tool",
        type: "tool",
        status: "running",
        isStreaming: true,
        partialToolArgs: { title: "Draft" },
      },
    ];
    const updatedMessages = [
      { ...initialMessages[0], partialToolArgs: { title: "Draft", content: "Text" } },
    ];

    expect(getStreamingFollowSignal(updatedMessages)).not.toBe(
      getStreamingFollowSignal(initialMessages),
    );
  });

  it("keeps following during a thinking block height animation", () => {
    expect(
      resolveFollowBottomStateOnScroll({
        previous: { scrollHeight: 1_000, scrollTop: 800, clientHeight: 200 },
        next: { scrollHeight: 1_100, scrollTop: 700, clientHeight: 200 },
        wasFollowingBottom: true,
        isAutoScrollPending: true,
      }),
    ).toBe(true);
  });

  it("stops following when the user scrolls upward without a pending automatic scroll", () => {
    expect(
      resolveFollowBottomStateOnScroll({
        previous: { scrollHeight: 1_000, scrollTop: 800, clientHeight: 200 },
        next: { scrollHeight: 1_100, scrollTop: 700, clientHeight: 200 },
        wasFollowingBottom: true,
      }),
    ).toBe(false);
  });
});
