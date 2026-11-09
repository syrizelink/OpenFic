import type { CapacitorConfig } from "@capacitor/cli";
const config: CapacitorConfig = {
  appId: "com.openfic.mobile",
  appName: "OpenFic",
  webDir: "dist",
  android: { allowMixedContent: false },
  ios: {
    contentInset: "always",
    scheme: "OpenFic",
  },
};
export default config;
