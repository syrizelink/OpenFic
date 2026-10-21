document.getElementById("resize").addEventListener("click", async () => {
  await window.OpenFic.ready;
  const height = await window.OpenFic.ui.resize(180);
  document.querySelector('[role="status"]').textContent = String(height);
});
