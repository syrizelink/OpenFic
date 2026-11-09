# iOS 构建指南

`mobile/` 基于 Capacitor，已包含 `ios/` 平台工程。构建需要 **macOS + Xcode**。

## 前置要求

- macOS + Xcode（App Store 免费安装）
- Node.js 22+、pnpm 11（`corepack enable` 或 `npm i -g pnpm@11`）
- 可选：CocoaPods（`npx cap sync ios` 会自动执行 `pod install`，未安装时会跳过并在 Xcode 打开时自动处理）

## 构建步骤

```bash
cd mobile
pnpm install
pnpm build        # 构建 WebView 资源到 dist/
pnpm sync:ios     # pnpm build + cap sync ios
pnpm ios          # 用 Xcode 打开工程
```

## Xcode 配置

1. 打开 `ios/App/App.xcworkspace`
2. **Signing & Capabilities** → 选择你的 Apple ID Team
   - 免费 Apple ID（Personal Team）即可真机调试，签名 7 天有效
   - 需要长期使用或给多台设备分发，建议加入 Apple Developer Program（$99/年，Ad Hoc 最多 100 台设备）
3. Bundle Identifier 默认 `com.openfic.mobile`，如与他人冲突请改为自己的域名反写

## 连接自建服务器

- iOS 的 ATS 默认禁止明文 HTTP。`ios/App/App/Info.plist` 已内置 `NSAllowsLocalNetworking` 豁免，可直接连接局域网地址（如 `http://192.168.1.10:8000`）
- 公网访问建议使用 HTTPS（如内置 tunnels 功能）；如确需明文公网地址，请按需在 Info.plist 补充 `NSExceptionDomains`
- 首次访问局域网地址时，iOS 会弹出「本地网络」权限请求，需要允许（`NSLocalNetworkUsageDescription` 已配置说明文案）

## 注意事项

- 仓库只包含源码工程，不包含签名证书 / Provisioning Profile，请勿提交个人信息
- `ios/App/App/public/`、`ios/App/App/capacitor.config.json`、`ios/App/App/capacitor.plugins.json` 为生成产物，已在 `.gitignore` 中忽略
- 修改 `mobile/src` 后需重新执行 `pnpm sync:ios` 再在 Xcode 中运行
