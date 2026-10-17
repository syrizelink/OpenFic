export function getSDK() {
  const sdk = globalThis.OpenFic;
  if (!sdk) throw new Error('Load the host sdk.js before starting the plugin application');
  return sdk;
}
export const OpenFic = new Proxy({}, { get: (_, key) => getSDK()[key] });
export default OpenFic;
