/* Render the supported Claude component tree in the isolated plugin iframe. */
const status = document.getElementById("status");
let context;
let panes = [];
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
  if (props.color) element.style.color = props.color;
  if (type === "Text") element.style.whiteSpace = "pre-wrap";
  if (type === "Box") {
    element.style.display = "flex";
    element.style.flexDirection = props.flexDirection || "column";
    element.style.gap = "6px";
    element.style.minWidth = "0";
    element.style.flexWrap = "wrap";
  }
  if (type === "Client") element.textContent = "Client renderer modules are not supported by this host.";
  return element;
}
function paint(result) {
  panes = result.panes || [];
  const trees = result.trees.filter((entry) => entry.tree != null);
  document.getElementById("render").replaceChildren(...trees.map((entry) => draw(entry.tree)));
  document.getElementById("render").dataset.empty = String(trees.length === 0);
}
async function inspect() {
  return OpenFic.call("mod.inspect", { slot: context.slot, columns: Math.floor(innerWidth / 9) });
}
async function runAction(id, value) {
  if (!id) return;
  try {
    await OpenFic.call("mod.action", { id, key: id, value });
    const result = await refresh();
    if (context.slot !== "sidebar.extensions" && result.panes.length) {
      const query = context.projectId ? "?projectId=" + encodeURIComponent(context.projectId) : "";
      await OpenFic.ui.navigate("/extensions/" + context.pluginId + "/mod" + query);
    }
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
  document.getElementById("title").textContent = context.pluginId;
  if (embedded) {
    document.getElementById("title").hidden = true;
    document.getElementById("commands").hidden = true;
    document.querySelector("main").style.padding = "8px";
  }
  try { await refresh(); } catch (error) { status.textContent = error.message; }
});
let refreshTimer;
window.addEventListener("keydown", async (event) => {
  const pane = panes.find((pane) => pane.closeOnEscape);
  if (event.key !== "Escape" || !pane) return;
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
