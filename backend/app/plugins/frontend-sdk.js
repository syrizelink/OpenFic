/* OpenFic view SDK v1. Views communicate only with their own host window. */
(() => {
  let channel;
  let context;
  let nextId = 0;
  const pending = new Map();
  let resolveReady;
  const ready = new Promise((resolve) => { resolveReady = resolve; });
  window.addEventListener("message", (event) => {
    if (event.source !== parent || !event.data || event.data.protocol !== "openfic.plugin.v1") return;
    const message = event.data;
    if (message.type === "init" && !channel) {
      channel = message.channel;
      context = Object.freeze(message.context);
      document.documentElement.dataset.theme = context.theme;
      document.documentElement.lang = context.language;
      resolveReady(context);
    } else if (message.type === "result" && message.channel === channel) {
      const call = pending.get(message.id);
      if (!call) return;
      clearTimeout(call.timer);
      pending.delete(message.id);
      if (message.error) call.reject(new Error(message.error));
      else call.resolve(message.result);
    }
  });
  window.OpenFic = Object.freeze({
    ready,
    getContext: () => context,
    async call(method, params = {}) {
      await ready;
      const id = String(++nextId);
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => { pending.delete(id); reject(new Error("Plugin request timed out")); }, 20000);
        pending.set(id, { resolve, reject, timer });
        parent.postMessage({ protocol: "openfic.plugin.v1", type: "call", channel, id, method, params }, "*");
      });
    },
  });
  parent.postMessage({ protocol: "openfic.plugin.v1", type: "ready" }, "*");
})();
