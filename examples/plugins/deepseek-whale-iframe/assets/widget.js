/* The bubble geometry and proportions are adapted from MeteorNOX's MIT-licensed widget. */
(() => {
  const $ = (id) => document.getElementById(id);
  const pet = $("pet"), root = $("whale"), bubble = $("bubble"), menu = $("menu");
  const config = { size: 250, x: null, y: null, snap: true, bubble: true };
  let viewport = { width: 0, height: 0 }, data = null, page = 0, drag = null;
  let pendingBounds = null, sending = false, lastTurn = null, desiredBounds = null;
  let menuPosition = null, menuArea = null, snapFrame = null;
  let appliedArea = null, pendingLayouts = [];

  function applyLayout(layout) {
    const { area, whale, menuRect } = layout;
    root.style.left = `${whale.x - area.x}px`;
    root.style.top = `${whale.y - area.y}px`;
    root.style.width = `${whale.width}px`;
    root.style.height = `${whale.height}px`;
    root.classList.toggle("left", whale.x <= 50);
    if (menuRect) {
      menu.style.left = `${menuRect.x - area.x}px`;
      menu.style.top = `${menuRect.y - area.y}px`;
      menu.style.width = `${menuRect.width}px`;
      menu.style.height = `${menuRect.height}px`;
      menu.style.visibility = "visible";
    }
    appliedArea = area;
  }
  function syncLayout() {
    const index = pendingLayouts.findLastIndex(({ area }) =>
      Math.abs(area.width - window.innerWidth) <= 1 && Math.abs(area.height - window.innerHeight) <= 1);
    if (index < 0) return;
    const layout = pendingLayouts[index];
    pendingLayouts = pendingLayouts.slice(index + 1);
    applyLayout(layout);
  }
  const resizeObserver = new ResizeObserver(syncLayout);
  resizeObserver.observe(document.documentElement);
  window.addEventListener("resize", syncLayout);
  window.addEventListener("pagehide", () => {
    if (snapFrame !== null) cancelAnimationFrame(snapFrame);
    resizeObserver.disconnect();
    window.removeEventListener("resize", syncLayout);
  }, { once: true });

  function bounds(requestedSize = config.size) {
    const size = Math.min(requestedSize, viewport.width, viewport.height);
    return { x: Math.max(0, Math.min(viewport.width - size, config.x ?? viewport.width - size - 12)),
      y: Math.max(0, Math.min(viewport.height - size, config.y ?? viewport.height - size - 32)), width: size, height: size };
  }
  async function updateBounds() {
    const whale = bounds();
    let area = { ...whale };
    let menuRect = null;
    if (!menu.hidden) {
      const width = Math.min(220, viewport.width);
      const height = Math.min(280, viewport.height);
      if (!menuPosition) {
        const leftSide = whale.x + whale.width / 2 < viewport.width / 2;
        const buttonLeft = whale.x + whale.width - 31;
        menuPosition = {
          x: Math.max(0, Math.min(viewport.width - width, leftSide ? buttonLeft : buttonLeft + 27 - width)),
          y: Math.max(0, Math.min(viewport.height - height, whale.y + whale.height * (1 - 0.5945) - height - 6)),
        };
      }
      menuPosition.x = Math.max(0, Math.min(viewport.width - width, menuPosition.x));
      menuPosition.y = Math.max(0, Math.min(viewport.height - height, menuPosition.y));
      if (!menuArea || whale.x < menuArea.x || whale.y < menuArea.y ||
          whale.x + whale.width > menuArea.x + menuArea.width || whale.y + whale.height > menuArea.y + menuArea.height) {
        const small = bounds(120), large = bounds(360);
        const left = Math.min(menuPosition.x, whale.x, small.x, large.x);
        const top = Math.min(menuPosition.y, whale.y, small.y, large.y);
        menuArea = { x: left, y: top,
          width: Math.max(menuPosition.x + width, whale.x + whale.width, small.x + small.width, large.x + large.width) - left,
          height: Math.max(menuPosition.y + height, whale.y + whale.height, small.y + small.height, large.y + large.height) - top };
      }
      area = menuArea;
      menuRect = { ...menuPosition, width, height };
    }
    const layout = { area, whale, menuRect };
    if (appliedArea && Math.abs(area.width - appliedArea.width) <= 1 && Math.abs(area.height - appliedArea.height) <= 1) {
      applyLayout(layout);
    } else {
      if (menuRect && !appliedArea) menu.style.visibility = "hidden";
      pendingLayouts.push(layout);
      if (pendingLayouts.length > 8) pendingLayouts.shift();
      syncLayout();
    }
    if (!desiredBounds || Object.keys(area).some((key) => area[key] !== desiredBounds[key])) {
      desiredBounds = area;
      pendingBounds = area;
    }
    if (sending) return;
    sending = true;
    try {
      while (pendingBounds) {
        const next = pendingBounds;
        pendingBounds = null;
        await OpenFic.ui.setOverlayBounds(next);
      }
    } catch (error) {
      desiredBounds = null;
      $("status").textContent = String(error.message || error);
    } finally { sending = false; }
  }
  function save() { return OpenFic.storage.set("whale.appearance", config); }
  function cancelSnap() {
    if (snapFrame === null) return false;
    cancelAnimationFrame(snapFrame);
    snapFrame = null;
    return true;
  }
  function snapTo(start, target) {
    if ((start.x === target.x && start.y === target.y) || matchMedia("(prefers-reduced-motion: reduce)").matches) {
      config.x = target.x; config.y = target.y;
      void updateBounds();
      void save();
      return;
    }
    const started = performance.now();
    function step(now) {
      const progress = Math.min(1, (now - started) / 160);
      const eased = 1 - (1 - progress) ** 3;
      config.x = start.x + (target.x - start.x) * eased;
      config.y = start.y + (target.y - start.y) * eased;
      void updateBounds();
      if (progress < 1) snapFrame = requestAnimationFrame(step);
      else { snapFrame = null; void save(); }
    }
    snapFrame = requestAnimationFrame(step);
  }
  function render() {
    if (!data) return;
    const balance = data.balance;
    const currency = balance?.currency || "";
    const pages = [
      ["余额", balance ? `${currency === "CNY" ? "¥" : currency + " "}${balance.total.toFixed(2)}` : "--", data.error || (balance?.stale ? "余额可能已过期" : "点击切换")],
      ["今日观测消费", balance ? `${currency === "CNY" ? "¥" : currency + " "}${data.today.toFixed(2)}` : "--", "余额变化，不等同账单"],
      ["上一轮对话", data.lastTurn ? `$${data.lastTurn.cost.toFixed(4)}` : "--", data.lastTurn ? `${data.lastTurn.tokens} tokens · USD` : "尚无回合费用"],
    ];
    const current = pages[page % pages.length];
    $("label").textContent = current[0];
    $("amount").textContent = current[1];
    $("hint").textContent = current[2];
    bubble.hidden = !config.bubble;
    $("show-bubble").checked = config.bubble;
    $("snap").checked = config.snap;
    $("size").value = config.size;
    if (balance && balance.total <= data.lowBalance) $("hint").textContent = "余额偏低，请留意充值";
    if (data.budget && data.today >= data.budget) $("hint").textContent = "今日观测消费已达到预算";
  }
  async function load() {
    try {
      const next = await OpenFic.call("whale.snapshot", {});
      if (next.lastTurn?.id && next.lastTurn.id !== lastTurn && lastTurn !== null) {
        page = 2;
        config.bubble = true;
      }
      lastTurn = next.lastTurn?.id || "";
      data = next;
      render();
    } catch (error) { $("status").textContent = String(error.message || error); }
  }
  pet.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    const interrupted = cancelSnap();
    const position = bounds();
    drag = { x: event.screenX, y: event.screenY, left: position.x, top: position.y, moved: false, interrupted };
    pet.setPointerCapture(event.pointerId);
  });
  pet.addEventListener("pointermove", (event) => {
    if (!drag) return;
    const dx = event.screenX - drag.x, dy = event.screenY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
    if (!drag.moved) return;
    config.x = drag.left + dx;
    config.y = drag.top + dy;
    void updateBounds();
  });
  async function finish(event, cancelled) {
    if (!drag) return;
    const previous = drag;
    drag = null;
    if (pet.hasPointerCapture(event.pointerId)) pet.releasePointerCapture(event.pointerId);
    if (cancelled) { config.x = previous.left; config.y = previous.top; }
    else if (previous.moved) {
      const current = bounds();
      const start = { x: current.x, y: current.y };
      if (config.snap) {
        if (current.x < 50) current.x = 0;
        else if (viewport.width - current.x - current.width < 50) current.x = viewport.width - current.width;
        if (viewport.height - current.y - current.height < 50) current.y = viewport.height - current.height;
      }
      snapTo(start, current);
      return;
    } else { config.bubble = true; page = (page + 1) % 3; render(); }
    if (previous.interrupted) await save();
    await updateBounds();
  }
  pet.addEventListener("pointerup", (event) => void finish(event, false));
  pet.addEventListener("pointercancel", (event) => void finish(event, true));
  pet.addEventListener("keydown", (event) => {
    const keys = { ArrowLeft: [-10, 0], ArrowRight: [10, 0], ArrowUp: [0, -10], ArrowDown: [0, 10] };
    if (!keys[event.key]) return;
    cancelSnap();
    event.preventDefault();
    const current = bounds();
    config.x = current.x + keys[event.key][0]; config.y = current.y + keys[event.key][1];
    void updateBounds();
    void save();
  });
  bubble.addEventListener("click", () => { page = (page + 1) % 3; render(); });
  $("menu-button").addEventListener("click", () => {
    menu.hidden = !menu.hidden;
    if (!menu.hidden) menu.style.visibility = "hidden";
    if (menu.hidden) { menuPosition = null; menuArea = null; }
    $("menu-button").setAttribute("aria-expanded", String(!menu.hidden));
    void updateBounds();
  });
  $("close-menu").addEventListener("click", () => { menu.hidden = true; menuPosition = null; menuArea = null; $("menu-button").setAttribute("aria-expanded", "false"); void updateBounds(); });
  for (const id of ["test-dialog", "test-popover"]) {
    $(id).addEventListener("click", async (event) => {
      try {
        if (id === "test-dialog") await OpenFic.ui.openOverlay(id);
        else {
          if (!appliedArea) throw new Error("浮层位置尚未就绪");
          const rect = event.currentTarget.getBoundingClientRect();
          await OpenFic.ui.openOverlay(id, { x: appliedArea.x + rect.x, y: appliedArea.y + rect.y, width: rect.width, height: rect.height });
        }
      } catch (error) { $("status").textContent = String(error.message || error); }
    });
  }
  $("size").addEventListener("input", (event) => { cancelSnap(); config.size = Number(event.target.value); void updateBounds(); });
  $("size").addEventListener("change", () => { menuPosition = null; menuArea = null; void updateBounds(); void save(); });
  $("show-bubble").addEventListener("change", (event) => { config.bubble = event.target.checked; render(); void save(); });
  $("snap").addEventListener("change", (event) => { config.snap = event.target.checked; void save(); });
  $("reset").addEventListener("click", () => { cancelSnap(); config.x = null; config.y = null; void updateBounds(); void save(); });
  $("refresh").addEventListener("click", async () => {
    $("status").textContent = "正在刷新…";
    try { const result = await OpenFic.call("whale.refresh", {}); await load(); $("status").textContent = result.ok ? "余额已刷新" : "余额未能刷新"; }
    catch (error) { $("status").textContent = String(error.message || error); }
  });
  $("correct").addEventListener("click", async () => {
    const value = $("correction").value;
    if (!value) { $("status").textContent = "请输入校正金额"; return; }
    try { await OpenFic.call("whale.correct", { amount: value }); await load(); $("status").textContent = "已保存校正"; }
    catch (error) { $("status").textContent = String(error.message || error); }
  });
  OpenFic.on("ui.invalidate", () => void load());
  OpenFic.on("ui.viewportChanged", (value) => { if (cancelSnap()) void save(); viewport = value; menuArea = null; void updateBounds(); });
  void (async () => {
    try {
      const context = await OpenFic.ready;
      viewport = context.viewport;
      const saved = await OpenFic.storage.get("whale.appearance", null);
      if (saved && typeof saved === "object") {
        if (Number.isFinite(saved.size)) config.size = Math.max(120, Math.min(360, saved.size));
        if (Number.isFinite(saved.x)) config.x = saved.x;
        if (Number.isFinite(saved.y)) config.y = saved.y;
        if (typeof saved.snap === "boolean") config.snap = saved.snap;
        if (typeof saved.bubble === "boolean") config.bubble = saved.bubble;
      }
      await updateBounds();
      await load();
    } catch (error) { $("status").textContent = String(error.message || error); }
  })();
})();
