# iOS 构建指南

`mobile/` 基于 Capacitor，已包含 `ios/` 平台工程。构建需要 **macOS + Xcode**。

## 前置要求

- macOS + Xcode 16+（App Store 免费安装），iOS 部署目标 14.0
- Node.js 22+、pnpm 11（`corepack enable` 或 `npm i -g pnpm@11`）
- **必需**：CocoaPods（`brew install cocoapods` 或 `sudo gem install cocoapods`）
  - `npx cap sync ios` 会自动执行 `pod install`
  - 若该步骤被跳过（例如未装 CocoaPods），需进入 `ios/App` 手动执行 `pod install`

## 构建步骤

```bash
cd mobile
pnpm install
pnpm --dir ../frontend install
pnpm sync:ios
pnpm ios
```

`pnpm sync:ios` 已包含 `pnpm build`（构建 WebView 资源到 `dist/`）与 `cap sync ios`，无需单独执行 `pnpm build`。

## Xcode 配置

1. 打开 `ios/App/App.xcworkspace`
2. **Signing & Capabilities** → 选择你的 Apple ID Team
   - 免费 Apple ID（Personal Team）即可真机调试，签名 7 天有效
   - 需要长期使用或给多台设备分发，建议加入 Apple Developer Program（$99/年，Ad Hoc 最多 100 台设备）
3. Bundle Identifier 默认 `com.openfic.mobile`，如与他人冲突请改为自己的域名反写

## 连接自建服务器

- iOS 版连接实例的方式：先用 `fetch` 做健康检查（`/api/v1/health`），再用 WebView 导航到该地址打开实例。iOS 侧**没有原生扫码**（扫码仅 Android 可用），原生 iOS 插件（专用 view controller）计划在后续迭代中补充
- iOS 的 ATS 默认禁止明文 HTTP。`ios/App/App/Info.plist` 已内置 `NSAllowsLocalNetworking` 豁免，但它**只覆盖本地地址**（局域网 IP 如 `http://192.168.1.10:8000`、`.local` 主机名）
- **公网 DDNS 的明文地址会被 ATS 拦截，必须使用 HTTPS**（可用内置 tunnels 功能）；这与 Android 的 `usesCleartextTraffic="true"` 能力不对等，是两端有意接受的差异
- 首次访问局域网地址时，iOS 会弹出「本地网络」权限请求，需要允许（`NSLocalNetworkUsageDescription` 已配置说明文案）；若误拒，可到「设置 → 隐私与安全性 → 本地网络」重新打开
- 真机调试需在设备上开启开发者模式（iOS 16+：[设置 → 隐私与安全性 → 开发者模式]）

## 注意事项

- 仓库只包含源码工程，不包含签名证书 / Provisioning Profile，请勿提交个人信息
- `ios/App/App/public/`、`ios/App/App/capacitor.config.json` 为生成产物，已在 `.gitignore` 中忽略（iOS 不生成 `capacitor.plugins.json`；`Podfile.lock`、`App.xcworkspace/contents.xcworkspacedata`、`App.xcodeproj/project.xcworkspace/` 同样已忽略）
- 修改 `mobile/src` 后需重新执行 `pnpm sync:ios` 再在 Xcode 中运行
