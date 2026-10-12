/* Standalone UI; no React imports, direct API access, or application internals. */
const $ = (id) => document.getElementById(id);
let language = "zh-CN";
let sequence = 0;
const text = (zh, en) => language.startsWith("zh") ? zh : en;
const number = (value) => new Intl.NumberFormat(language).format(value);

async function refresh() {
  const request = ++sequence;
  $("refresh").disabled = true;
  $("report").hidden = true;
  $("message").textContent = text("正在加载…", "Loading…");
  try {
    const selected = $("project").value;
    if (!selected) { $("message").textContent = text("暂无项目，请先创建项目。", "Create a project to see statistics."); return; }
    const data = await OpenFic.call("statistics.get", { projectId: selected });
    if (request !== sequence) return;
    $("project-title").textContent = data.project.title;
    $("metrics").replaceChildren();
    const metrics = [
      [text("总字数", "Words"), data.words], [text("章节", "Chapters"), data.chapters],
      [text("卷", "Volumes"), data.volumes], [text("角色", "Characters"), data.characters],
      [text("世界书条目", "World entries"), data.worldEntries], [text("笔记", "Notes"), data.notes],
      [text("平均章节字数", "Average chapter words"), data.averageChapterWords],
      [text("启用世界书条目", "Enabled world entries"), data.enabledWorldEntries],
    ];
    for (const [label, value] of metrics) {
      const card = document.createElement("article");
      const name = document.createElement("span"); name.textContent = label;
      const amount = document.createElement("strong"); amount.textContent = number(value);
      card.append(name, amount); $("metrics").append(card);
    }
    $("progress").value = data.progress;
    $("goal").textContent = `${number(data.words)} / ${number(data.targetWords)} · ${data.progress}%`;
    $("volume-body").replaceChildren();
    for (const volume of data.volumeDistribution) {
      const row = document.createElement("tr");
      for (const value of [volume.title, number(volume.chapters), number(volume.words), `${data.words ? (volume.words / data.words * 100).toFixed(1) : 0}%`]) {
        const cell = document.createElement("td"); cell.textContent = value; row.append(cell);
      }
      $("volume-body").append(row);
    }
    $("volumes").hidden = !data.volumeDistribution.length;
    $("updated").textContent = text("项目最后更新：", "Project updated: ") + new Date(data.project.updated_at).toLocaleString(language);
    $("message").textContent = text("统计已更新，包含已保存的数据。", "Statistics updated from saved data.");
    $("report").hidden = false;
  } catch (error) { if (request === sequence) $("message").textContent = error.message; }
  finally { if (request === sequence) $("refresh").disabled = false; }
}

OpenFic.ready.then(async (context) => {
  language = context.language || "zh-CN";
  for (const [id, zh, en] of [
    ["heading", "项目统计", "Project statistics"], ["refresh", "刷新", "Refresh"],
    ["project-label", "选择项目", "Select project"], ["goal-title", "写作目标", "Writing goal"],
    ["volume-title", "各卷统计", "Volume distribution"], ["volume-name", "卷", "Volume"],
    ["volume-chapters", "章节", "Chapters"], ["volume-words", "字数", "Words"], ["volume-share", "占比", "Share"],
  ]) $(id).textContent = text(zh, en);
  $("refresh").addEventListener("click", initialize);
  $("project").addEventListener("change", refresh);
  await initialize();
}).catch((error) => { $("message").textContent = error.message; });

async function initialize() {
  $("refresh").disabled = true;
  try {
    const projects = await OpenFic.call("projects.list");
    const selected = $("project").value || OpenFic.getContext().projectId;
    $("project").replaceChildren();
    for (const project of projects) {
      const option = document.createElement("option"); option.value = project.id; option.textContent = project.title; $("project").append(option);
    }
    if (projects.some((project) => project.id === selected)) $("project").value = selected;
    await refresh();
  } catch (error) { $("report").hidden = true; $("message").textContent = error.message; }
  finally { $("refresh").disabled = false; }
}
