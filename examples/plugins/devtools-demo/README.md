# SDK Devtools 示例

本示例只使用公共 SDK，提供四个视图：原生独立页面、编辑器工具栏按钮、全局浮层及独立 iframe 前端。清单版本保持 1.0.0，便于观察同版本开发重载。普通生产更新仍须递增版本。

```bash
# 先安装插件自己配置的前端检查工具
cd examples/plugins/devtools-demo/frontend
pnpm install
cd ../../../..
# 检查并执行真实 Ruff/Oxlint/TypeScript；缺少工具或未执行检查会失败
openfic plugin check examples/plugins/devtools-demo --run-checks --strict
# 启动独立数据的开发服务，打开输出的 /extensions/devtools
openfic plugin dev examples/plugins/devtools-demo
# 或生成可直接安装的 ZIP
openfic plugin pack examples/plugins/devtools-demo --output /tmp/devtools-demo.zip --run-checks --strict
```

仓库开发可以在 backend 中以 `uv run python -m app.cli` 替代 openfic，并按当前位置调整源码路径。前端项目通过本地 file: 依赖引用仓库 SDK；复制到其他仓库时请修改该依赖路径。

“增加计数”写入真实插件存储；“触发权限错误”请求未声明的 projects.read；“触发 CSS 诊断”添加宿主不允许的 @import；“验证密钥脱敏”返回测试配置中的 secret，供 Inspector 验证它不会进入记录。API Key 字段仅为诊断测试，不连接任何外部服务，请使用测试字符串。

iframe 前端使用自己的 Oxlint 和 TypeScript 配置。脚本通过 crossorigin="anonymous" 加载，使沙箱内的浏览器 error 事件能提供详细信息；未放开 sandbox 同源权限或 CSP。其按钮演示 SDK 存储和刻意抛出的前端异常。

编辑 backend/main.py 或 frontend 文件，观察 reload revision、UI 和保留的计数。尝试传入非法 Props 或使后端激活失败，预览应继续使用旧实现，开发页显示错误；修复后恢复。`.openfic-dev/` 是独立数据目录，不会打入包。

`plugin.dev.json` 引用 `ui/overview.json` 进行静态协议校验。动态渲染、各按钮行为和其他视图仍由真实预览与端到端测试覆盖，单个 fixture 不代表完整业务验证。
