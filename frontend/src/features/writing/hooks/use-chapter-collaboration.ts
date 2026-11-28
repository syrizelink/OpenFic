import * as decoding from "lib0/decoding";
import * as encoding from "lib0/encoding";
import { useEffect, useState } from "react";
import { IndexeddbPersistence } from "y-indexeddb";
import { WebsocketProvider } from "y-websocket";
import * as Y from "yjs";

import { apiClient, getApiBaseUrl } from "@/lib/api-client";

export interface ChapterCollaboration {
  document: Y.Doc;
  ready: boolean;
  status: "connecting" | "synced" | "pending" | "offline";
  error?: string;
  markPending: () => void;
  flush: () => void;
}

export function useChapterCollaboration(chapterId: string) {
  const [collaboration, setCollaboration] = useState<ChapterCollaboration | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let disposed = false;
    let provider: WebsocketProvider | undefined;
    let persistence: IndexeddbPersistence | undefined;
    const document = new Y.Doc();
    const update = (patch: Partial<ChapterCollaboration>) => {
      if (!disposed) setCollaboration((current) => (current ? { ...current, ...patch } : current));
    };
    void (async () => {
      try {
        const { data } = await apiClient.post<{ room: string }>(
          `/collaboration/chapters/${chapterId}/session`,
        );
        if (disposed) return;
        const url = new URL(
          `${getApiBaseUrl()}/collaboration/chapters/${chapterId}`,
          window.location.origin,
        );
        url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
        persistence = new IndexeddbPersistence(
          `openfic-collaboration:${url.host}:${data.room}`,
          document,
        );
        await persistence.whenSynced;
        if (disposed) return;
        provider = new WebsocketProvider(url.toString(), data.room.split(":")[1], document, {
          connect: false,
          disableBc: true,
        });
        const activeProvider = provider;
        const flush = () => {
          if (!activeProvider.wsconnected || !activeProvider.ws) return;
          const message = encoding.createEncoder();
          encoding.writeVarUint(message, 4);
          encoding.writeVarString(message, JSON.stringify({ type: "flush" }));
          activeProvider.ws.send(encoding.toUint8Array(message));
        };
        // Extend the standard Yjs wire protocol with a durable-save acknowledgement.
        activeProvider.messageHandlers[4] = (_encoder, decoder) => {
          const message = JSON.parse(decoding.readVarString(decoder)) as {
            type: string;
            vector?: number[];
            content?: string;
            message?: string;
          };
          if (message.type === "saved" && message.vector) {
            const vector = Y.encodeStateVector(document);
            const content = document
              .getXmlFragment("default")
              .toArray()
              .map((paragraph) =>
                paragraph instanceof Y.XmlElement
                  ? paragraph
                      .toArray()
                      .map((text) => (text instanceof Y.XmlText ? text.toString() : ""))
                      .join("")
                  : "",
              )
              .join("\n");
            if (
              message.content === content &&
              message.vector.length === vector.length &&
              message.vector.every((byte, index) => byte === vector[index])
            ) {
              update({ status: "synced", error: undefined });
            }
          } else if (message.type === "error") {
            update({ status: "offline", error: message.message });
          }
        };
        activeProvider.on("sync", (synced) => {
          if (synced) {
            update({ ready: true, status: "pending" });
            flush();
          }
        });
        activeProvider.on("status", ({ status }) => {
          if (status !== "connected") update({ status: "offline" });
        });
        activeProvider.on("connection-close", (event) => {
          if (event?.code === 1008)
            update({ status: "offline", error: "协同文档不可用，请重新打开章节" });
        });
        setCollaboration({
          document,
          ready: false,
          status: "connecting",
          flush,
          markPending: () => update({ status: activeProvider.wsconnected ? "pending" : "offline" }),
        });
        activeProvider.connect();
      } catch (failure) {
        if (!disposed) setError(failure instanceof Error ? failure.message : String(failure));
      }
    })();
    return () => {
      disposed = true;
      provider?.destroy();
      void persistence?.destroy();
      document.destroy();
    };
  }, [chapterId]);
  return { collaboration, error };
}
