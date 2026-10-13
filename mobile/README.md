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

APK 生成于 `out/OpenFic-<版本>-android.apk`。当前命令生成可安装的 **debug 签名测试包**；正式发布需要配置自己的 release 签名密钥，执行 Gradle `assembleRelease` / `bundleRelease`，并在以后版本中持续使用同一密钥。

浏览器 UI 预览：`pnpm dev`。浏览器预览不能打开 Android 原生实例页面。

## 实现

- `src/`：连接列表、健康检查、浅色/深色主题，直接导入前端现有样式。
- `scripts/copy-frontend.mjs`：将前端构建结果复制到 APK 资源目录，加入 mobile 标记并关闭 PWA service worker。
- `android/`：Capacitor 项目、远程实例插件与实例 WebView。
- `InstanceActivity`：在所选远程实例的 origin 下拦截并提供 APK 中的 React 静态资源。API、图片、文件上传、流式响应和 Socket.IO 直接访问该实例，从而维持 HttpOnly / SameSite Cookie 登录。页面和资源不依赖远程实例提供前端构建文件。
- 原生处理返回键、键盘与系统栏边距、系统文件选择、HTTP 下载以及 Blob 导出的文件保存。外部链接交由系统浏览器打开。实例 WebView 不提供 Capacitor bridge；文件保存使用仅限当前实例 origin 与主 frame 的消息通道，再由系统保存对话框确认。

前端业务代码仅增加 `openficMobileHost` 的 service worker 跳过条件。前端版本与服务器 API 应保持兼容；升级前端后需重新构建 APK。

## 验证与平台范围

连接配置测试覆盖 URL 校验与损坏记录恢复；Android 单元测试覆盖原生 URL 校验。构建时可执行 `cd android && ./gradlew testDebugUnitTest lintDebug`。

当前交付 Android 壳层；Android 7.0+（API 24）可安装。Capacitor 本身支持 iOS，但本实现的同源 WebView 适配是 Android 原生代码，iOS 需要另外实现 WKWebView 的对应能力，并使用 macOS/Xcode 构建。
