import { HocuspocusProvider } from "@hocuspocus/provider";
import { useEffect, useState } from "react";
import { IndexeddbPersistence } from "y-indexeddb";
import * as Y from "yjs";

import { apiClient, getApiBaseUrl } from "@/lib/api-client";

export interface ChapterCollaboration {
  document: Y.Doc;
  provider: HocuspocusProvider;
  ready: boolean;
  status: "connecting" | "synced" | "pending" | "offline";
  markPending: () => void;
}

export function useChapterCollaboration(chapterId: string) {
  const [collaboration, setCollaboration] = useState<ChapterCollaboration | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let disposed = false;
    let provider: HocuspocusProvider | undefined;
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
          `${getApiBaseUrl()}/collaboration/chapters/${chapterId}/${data.room.split(":")[1]}`,
          window.location.origin,
        );
        url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
        persistence = new IndexeddbPersistence(
          `openfic-collaboration:${url.host}:${data.room}`,
          document,
        );
        await persistence.whenSynced;
        if (disposed) return;
        provider = new HocuspocusProvider({
          url: url.toString(),
          name: data.room,
          document,
          onSynced: ({ state }) => {
            if (state) update({ ready: true, status: "pending" });
          },
          onStatus: ({ status }) => {
            if (status !== "connected") update({ status: "offline" });
          },
          onAuthenticationFailed: ({ reason }) => {
            if (!disposed) setError(reason);
          },
          onStateless: ({ payload }) => {
            try {
              const message = JSON.parse(payload) as {
                type: string;
                vector?: number[];
                content?: string;
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
                )
                  update({ status: "synced" });
              } else if (message.type === "error") update({ status: "offline" });
            } catch {
              /* Ignore unrelated awareness messages. */
            }
          },
        });
        const activeProvider = provider;
        setCollaboration({
          document,
          provider,
          ready: false,
          status: "connecting",
          markPending: () =>
            update({
              status:
                activeProvider.configuration.websocketProvider.status === "connected"
                  ? "pending"
                  : "offline",
            }),
        });
        provider.on("synced", () => provider?.sendStateless(JSON.stringify({ type: "flush" })));
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
