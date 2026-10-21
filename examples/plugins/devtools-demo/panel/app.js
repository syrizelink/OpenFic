// @ts-check
/** @type {import('@openfic/plugin-sdk').OpenFicSDK} */
const sdk = /** @type {Window & { OpenFic: import('@openfic/plugin-sdk').OpenFicSDK }} */ (window).OpenFic;
void sdk.ready.then(async () => {
  const value = document.getElementById("value");
  const button = document.getElementById("increment");
  const failure = document.getElementById("failure");
  if (!value || !button || !failure) throw new Error("Missing demo elements");
  let count = Number(await sdk.storage.get("iframe-count", 0));
  value.textContent = `iframe 计数：${count}`;
  button.addEventListener("click", () => {
    count++;
    void sdk.storage.set("iframe-count", count).then(() => { value.textContent = `iframe 计数：${count}`; });
  });
  failure.addEventListener("click", () => { throw new Error("Intentional iframe development error"); });
});
