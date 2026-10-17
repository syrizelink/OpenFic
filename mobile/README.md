# OpenFic Mobile

与 `desktop/` 并列的 Capacitor Android 壳层。复用 `frontend/` 的 React 应用、手机布局、Radix 组件和样式变量，只连接远程实例，不安装 Python 或启动本地后端。

## 安装包

本分支随代码提交了 [Android APK](releases/OpenFic-0.12.1-android.apk) 和 [SHA-256 校验文件](releases/OpenFic-0.12.1-android.apk.sha256)。这是 Android 7.0+ 可安装的 debug 签名测试包，尚未进行真机验证。

## 使用

安装 APK 后，输入实例名称（可选）与服务器根地址，例如 `https://openfic.example.com` 或 `http://192.168.1.20:8000`。验证成功后点击“打开实例”，有密码的实例会显示原有登录页。连接记录保存在手机中；可以通过页面顶部“实例”返回列表、添加或移除连接。移除连接不会删除服务器数据。

地址须为根地址，不支持部署在子路径下的实例。不能使用手机本机的 localhost/回环地址。局域网服务器需要监听可访问的网络接口；HTTPS 证书必须有效。HTTP 适合可信局域网。

## 构建

需要 Node.js 22+、pnpm、完整 JDK 21，以及 Android SDK Platform 35 / Build Tools 35.0.0。可以通过 Android Studio 安装 SDK。配置 `ANDROID_HOME` 或 `android/local.properties` 的 `sdk.dir`。

```sh
cd mobile
pnpm install --frozen-lockfile
pnpm type-check
pnpm test
pnpm apk
```

APK 生成于 `out/OpenFic-<版本>-android-debug.apk`，为 **debug 签名测试包**。正式签名构建使用 `pnpm apk:release`，需要设置 `ANDROID_KEYSTORE_PATH`、`ANDROID_KEYSTORE_PASSWORD`、`ANDROID_KEY_ALIAS`、`ANDROID_KEY_PASSWORD`。正式产物为 `out/OpenFic-<版本>-android.apk` 和 `out/android-update.json`，以后版本必须持续使用同一签名密钥。

## 自动更新与发布

Android APP 启动后检查 `syrizelink/OpenFic` 的最新正式 GitHub Release，自动下载安装包（包括计费网络，不使用漫游网络）。系统下载管理器负责下载；退出应用或重启后可恢复下载状态。下载完成后校验 SHA-256、大小、应用 ID、版本和签名，再提示打开系统安装界面。Android 不允许普通应用静默安装；首次需要授权“允许安装未知应用”，返回 APP 后再次点击安装。浏览器预览不提供更新功能。

`v*` 标签触发的 Package workflow 会构建正式 APK，并将安装包及 `android-update.json` 上传到对应 Release；移动发布不依赖桌面构建结果。仓库需要配置以下 GitHub Actions Secrets：

- `ANDROID_KEYSTORE_BASE64`：正式 keystore 文件的 Base64 内容。
- `ANDROID_KEYSTORE_PASSWORD`：keystore 密码。
- `ANDROID_KEY_ALIAS`：签名密钥别名。
- `ANDROID_KEY_PASSWORD`：签名密钥密码。

缺少签名配置会导致发布失败，不会回退为 debug 签名。`versionName` 来自 `mobile/package.json`，由 release-please 同步；`versionCode` 按 `major × 1000000 + minor × 1000 + patch` 生成，minor、patch 不超过 999，仅发布稳定版本。此前提交的 debug 测试包不能覆盖安装正式签名包，需要先卸载测试包再安装正式版；卸载会清除本机连接记录，但不会删除远程创作数据。

浏览器 UI 预览：`pnpm dev`。浏览器预览不能打开 Android 原生实例页面。

## 实现

- `src/`：连接列表、健康检查、浅色/深色主题，直接导入前端现有样式。
- `scripts/copy-frontend.mjs`：将前端构建结果复制到 APK 资源目录，加入 mobile 标记并关闭 PWA service worker。
- `android/`：Capacitor 项目、远程实例插件与实例 WebView。
- `InstanceActivity`：在所选远程实例的 origin 下拦截并提供 APK 中的 React 静态资源。API、图片、文件上传、流式响应和 Socket.IO 直接访问该实例，从而维持 HttpOnly / SameSite Cookie 登录。页面和资源不依赖远程实例提供前端构建文件。
- 原生处理返回键、键盘与系统栏边距、系统文件选择、HTTP 下载以及 Blob 导出的文件保存。外部链接交由系统浏览器打开。实例 WebView 不提供 Capacitor bridge；文件保存使用仅限当前实例 origin 与主 frame 的消息通道，再由系统保存对话框确认。

前端业务代码仅增加 `openficMobileHost` 的 service worker 跳过条件。前端版本与服务器 API 应保持兼容；升级前端后需重新构建 APK。

## 验证与平台范围

`pnpm test` 覆盖 URL 校验、损坏记录恢复、版本递增与 Release 更新清单；Android 单元测试覆盖原生 URL、更新来源、版本与安装包完整性校验。构建时可执行 `cd android && ./gradlew testDebugUnitTest lintDebug`。下载恢复、未知来源授权、签名不匹配及覆盖安装仍需在真机上验证。

当前交付 Android 壳层；Android 7.0+（API 24）可安装。Capacitor 本身支持 iOS，但本实现的同源 WebView 适配是 Android 原生代码，iOS 需要另外实现 WKWebView 的对应能力，并使用 macOS/Xcode 构建。
