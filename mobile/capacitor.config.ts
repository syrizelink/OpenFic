import type { CapacitorConfig } from "@capacitor/cli";
const config: CapacitorConfig = {
  appId: "com.openfic.mobile",
  appName: "OpenFic",
  webDir: "dist",
  android: { allowMixedContent: false },
};
export default config;
