(() => {
  document.getElementById("close").addEventListener("click", () => {
    void OpenFic.ui.close().catch((error) => { document.getElementById("status").textContent = error.message; });
  });
  void OpenFic.ready.then(() => { document.getElementById("close").disabled = false; });
})();
