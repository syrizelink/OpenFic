export function getSDK() {
  const sdk = globalThis.OpenFic;
  if (!sdk) throw new Error('The host initializes the SDK before loading a plugin view; open this application through an installed plugin view');
  return sdk;
}
export const OpenFic = new Proxy({}, { get: (_, key) => getSDK()[key] });
export default OpenFic;
