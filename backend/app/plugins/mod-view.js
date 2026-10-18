/* Render the supported Claude component tree in the isolated plugin iframe. */
const status = document.getElementById("status");
let context;
let panes = [];
let lastHeight = -1;
let paneKey = "";
function resizeToContent(force = false) {
  if (!context || context.slot === "sidebar.extensions") return;
  const main = document.querySelector("main");
  const height = Math.ceil(main.getBoundingClientRect().height);
  if (height === lastHeight && force !== true) return;
  lastHeight = height;
  OpenFic.ui.resize(height).catch((error) => { status.textContent = error.message; });
}
function draw(node) {
  if (node == null || node === false) return document.createTextNode("");
  if (Array.isArray(node)) {
    const box = document.createElement("div");
    node.forEach((child) => box.append(draw(child)));
    return box;
  }
  if (typeof node !== "object") return document.createTextNode(String(node));
  const props = node.props || {};
  const type = node.type || node.tag || "Box";
  if (!node.type && !node.tag) return document.createTextNode(node.text || "");
  const tag = { Text: "span", Box: "div", Button: "button", Input: "input", Select: "select", Code: "pre", Markdown: "pre", Link: "a" }[type] || "div";
  const element = document.createElement(tag);
  if (type === "Button") {
    element.textContent = props.label || "Run";
    element.disabled = Boolean(props.disabled);
    if (props.hotkey) element.dataset.hotkey = props.hotkey;
    if (props.autoFocus) element.dataset.autoFocus = "true";
    element.onclick = () => runAction(props.onPress);
  } else if (type === "Input") {
    element.placeholder = props.placeholder || "";
    element.value = props.value || "";
    element.onchange = () => runAction(props.onInput || props.onSubmit, element.value);
  } else if (type === "Select") {
    for (const option of props.options || []) {
      const item = document.createElement("option");
      item.value = option.value;
      item.textContent = option.label || option.value;
      element.append(item);
    }
    element.value = props.value || "";
    element.onchange = () => runAction(props.onSelect, element.value);
  } else if (type === "Link") {
    try {
      const url = new URL(props.href);
      if (["https:", "http:"].includes(url.protocol)) {
        element.href = url.href;
        element.target = "_blank";
        element.rel = "noopener noreferrer";
      }
    } catch {}
    element.textContent = props.label || props.href;
  } else if (props.text || props.source) {
    element.textContent = props.text || props.source;
  } else {
    for (const child of [node.children || props.children || []].flat()) element.append(draw(child));
  }
  if (props.bold) element.style.fontWeight = "bold";
  if (props.dimColor) element.style.opacity = "0.65";
  if (props.color) {
    const palette = document.documentElement.dataset.theme === "dark"
      ? { yellow: "#e2c072", blue: "#89b4fa", cyan: "#7ed5de", magenta: "#d3a2df", red: "#f78b8b", green: "#a6d189" }
      : { yellow: "#8a6500", blue: "#365dba", cyan: "#087b83", magenta: "#944ca8", red: "#bd3030", green: "#247443" };
    element.style.color = palette[props.color] || props.color;
  }
  if (props.inverse) { element.style.fontWeight = "bold"; element.style.background = "#8883"; }
  if (type === "Text") element.style.whiteSpace = "pre-wrap";
  if (type === "Box") {
    element.style.display = "flex";
    element.style.flexDirection = props.flexDirection || "column";
    if (props.justifyContent) element.style.justifyContent = props.justifyContent;
    if (props.alignItems) element.style.alignItems = props.alignItems;
    element.style.gap = (Number(props.gap) || 0) * 4 + "px";
    if (props.marginTop) element.style.marginTop = Number(props.marginTop) * 4 + "px";
    element.style.minWidth = "0";
    element.style.flexWrap = "wrap";
  }
  if (type === "Client") element.textContent = "Client renderer modules are not supported by this host.";
  return element;
}
function paint(result) {
  const focused = document.hasFocus() && document.activeElement?.tagName === "BUTTON" ? document.activeElement.textContent : null;
  panes = result.panes || [];
  const trees = result.trees.filter((entry) => entry.tree != null);
  document.getElementById("render").replaceChildren(...trees.map((entry) => {
    const section = document.createElement("section");
    section.dataset.component = entry.component;
    if (entry.component === "Pane") {
      section.setAttribute("role", "region");
      section.setAttribute("aria-label", panes.find((pane) => pane.id === entry.requestId)?.title || context.pluginId);
    } else section.setAttribute("aria-live", "polite");
    section.append(draw(entry.tree));
    return section;
  }));
  document.getElementById("render").dataset.empty = String(trees.length === 0);
  const nextKey = panes.map((pane) => pane.id).join("/");
  if (nextKey && nextKey !== paneKey && panes.some((pane) => pane.focus)) {
    document.querySelector('button[data-auto-focus="true"]')?.focus();
  } else if (focused) {
    [...document.querySelectorAll("button")].find((button) => button.textContent === focused)?.focus();
  }
  paneKey = nextKey;
  resizeToContent();
}
async function inspect() {
  return OpenFic.call("mod.inspect", { slot: context.slot, columns: Math.floor(innerWidth / 7.2) });
}
async function runAction(id, value) {
  if (!id) return;
  try {
    await OpenFic.call("mod.action", { id, key: id, value });
    await refresh();
  } catch (error) { status.textContent = error.message; }
}
async function refresh() {
  const result = await inspect();
  status.textContent = (result.compatibility.warnings || []).join("\n");
  const commands = document.getElementById("commands");
  commands.replaceChildren();
  for (const command of result.commands) {
    const button = document.createElement("button");
    button.textContent = "/" + command.name;
    button.onclick = async () => {
      try {
        const result = await OpenFic.call("mod.command", { command: command.name, args: "" });
        status.textContent = result?.text || JSON.stringify(result);
        paint(await inspect());
      } catch (error) { status.textContent = error.message; }
    };
    commands.append(button);
  }
  paint(result);
  return result;
}
OpenFic.ready.then(async (value) => {
  context = value;
  const embedded = context.slot !== "sidebar.extensions";
  document.documentElement.dataset.embedded = String(embedded);
  document.getElementById("title").textContent = context.pluginId;
  if (embedded) {
    document.getElementById("title").hidden = true;
    document.getElementById("commands").hidden = true;
  }
  new ResizeObserver(resizeToContent).observe(document.querySelector("main"));
  window.addEventListener("resize", () => resizeToContent(true));
  try { await refresh(); } catch (error) { status.textContent = error.message; }
});
let refreshTimer;
window.addEventListener("keydown", async (event) => {
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  const pane = panes.find((pane) => pane.closeOnEscape);
  if (event.key !== "Escape") {
    if (document.activeElement?.matches("input,textarea,[contenteditable=true]")) return;
    const button = [...document.querySelectorAll("button[data-hotkey]")].find((button) => button.dataset.hotkey.toLowerCase() === event.key.toLowerCase());
    if (button) { event.preventDefault(); button.click(); }
    return;
  }
  if (!pane) return;
  event.preventDefault();
  try {
    await OpenFic.call("mod.close", { id: pane.id });
    await refresh();
  } catch (error) { status.textContent = error.message; }
});
OpenFic.on("ui.invalidate", () => {
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => refresh().catch((error) => { status.textContent = error.message; }), 50);
});
