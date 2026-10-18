/* OpenFic SDK 2.0: framework-independent, isolated iframe transport. */
(() => {
  let channel, context, nextId = 0, resolveReady;
  const pending = new Map(), subscribers = new Map();
  const ready = new Promise(resolve => { resolveReady = resolve; });
  function on(event, listener) {
    if (!subscribers.has(event)) subscribers.set(event, new Set());
    subscribers.get(event).add(listener);
    return () => subscribers.get(event)?.delete(listener);
  }
  window.addEventListener("message", event => {
    const m = event.data;
    if (event.source !== parent || !m || m.protocol !== "openfic.plugin.v1") return;
    if (m.type === "init") {
      if (channel && m.channel !== channel) return;
      channel = m.channel; context = m.context;
      document.documentElement.dataset.theme = context.theme;
      document.documentElement.lang = context.language;
      resolveReady(context);
      for (const fn of subscribers.get("context.changed") || []) fn(context);
    } else if (m.channel === channel && m.type === "result") {
      const p = pending.get(m.id); if (!p) return;
      clearTimeout(p.timer); pending.delete(m.id);
      m.error ? p.reject(new Error(m.error)) : p.resolve(m.result);
    } else if (m.channel === channel && m.type === "event") {
      for (const fn of [...(subscribers.get(m.event) || []), ...(subscribers.get("*") || [])]) {
        try { fn(m.data, m.event); } catch (e) { console.error(e); }
      }
    }
  });
  async function call(method, params = {}) {
    await ready;
    const id = String(++nextId);
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { pending.delete(id); reject(new Error("Plugin request timed out")); }, 125000);
      pending.set(id, { resolve, reject, timer });
      parent.postMessage({ protocol: "openfic.plugin.v1", channel, type: "call", id, method, params }, "*");
    });
  }
  const remote = (name, params) => call("sdk." + name, params);
  const local = (name, params) => call("host." + name, params);
  const store = name => ({
    get: (key, fallback = null) => remote(name + ".get", { key, default: fallback }),
    set: (key, value) => remote(name + ".set", { key, value }),
    delete: key => remote(name + ".delete", { key }),
    keys: (prefix = "") => remote(name + ".keys", { prefix }),
  });
  const request = (method, path, options = {}) => remote("api.request", { method, path, ...options });
  const resource = name => ({
    list: (projectId, query = {}) => request("GET", projectId ? `/projects/${encodeURIComponent(projectId)}/${name}` : `/${name}`, { query }),
    get: id => request("GET", `/${name}/${encodeURIComponent(id)}`),
    create: (values, projectId) => request("POST", projectId ? `/projects/${encodeURIComponent(projectId)}/${name}` : `/${name}`, name === "projects" ? { form: values } : { json: values }),
    update: (id, values) => request("PATCH", `/${name}/${encodeURIComponent(id)}`, { json: values }),
    delete: id => request("DELETE", `/${name}/${encodeURIComponent(id)}`),
  });
  window.OpenFic = Object.freeze({
    version: "2.0.0", ready, getContext: () => context, call, on, resource,
    api: { request, catalogue: () => remote("catalogue", {}) },
    data: { projects: () => remote("data.projects", {}), entities: projectId => remote("data.entities", { projectId }) },
    projects: resource("projects"), chapters: resource("chapters"), volumes: resource("volumes"),
    notes: resource("notes"), characters: resource("characters"),
    storage: store("storage"), secrets: { set: store("secrets").set, delete: store("secrets").delete, keys: store("secrets").keys },
    files: { read: name => remote("files.read", { name }), write: (name, text) => remote("files.write", { name, text }), list: (name = "") => remote("files.list", { name }), delete: name => remote("files.delete", { name }) },
    http: { request: (method, url, options = {}) => remote("http.request", { method, url, ...options }) },
    models: { complete: (messages, model_id, options = {}) => remote("models.complete", { messages, model_id, ...options }) },
    workflow: { select: (projectId, provider) => remote("workflow.select", { projectId, provider }) },
    hooks: { preview: (event, data) => remote("hooks.preview", { event, data }) },
    events: { on, emit: (event, data = {}) => remote("events.emit", { event, data }) },
    editor: { read: () => local("editor.read", {}), insert: text => local("editor.insert", { text }), replaceSelection: text => local("editor.replaceSelection", { text }), setContent: text => local("editor.setContent", { text }), setSelection: (from, to) => local("editor.setSelection", { from, to }), focus: () => local("editor.focus", {}), save: () => local("editor.save", {}), undo: () => local("editor.undo", {}), redo: () => local("editor.redo", {}) },
    ui: { resize: height => local("ui.resize", { height }), navigate: path => local("ui.navigate", { path }), openExternal: url => local("ui.openExternal", { url }), toast: text => local("ui.toast", { text }), confirm: text => local("ui.confirm", { text }), copy: text => local("ui.copy", { text }), download: (name, text, mime) => local("ui.download", { name, text, mime }), context: () => local("ui.context", {}), invalidate: () => local("ui.invalidate", {}) },
    assistant: { fill: text => local("assistant.fill", { text }) },
    agent: { tools: () => remote("agent.tools", {}), start: (project_id, model_id, options = {}) => remote("agent.start", {project_id,model_id,...options}), send: (session_id,message,options = {}) => remote("agent.send",{session_id,message,...options}), cancel: session_id => remote("agent.cancel",{session_id}) },
    log: (message, level = "info") => remote("log", { message, level }),
  });
  parent.postMessage({ protocol: "openfic.plugin.v1", type: "ready" }, "*");
})();
