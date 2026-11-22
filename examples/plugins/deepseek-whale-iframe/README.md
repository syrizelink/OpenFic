# DeepSeek 小鲸鱼 iframe 示例

独立的 OpenFic 插件，参考 [MeteorNOX/DeepSeek-Balance-Whale-Widget](https://github.com/MeteorNOX/DeepSeek-Balance-Whale-Widget) 的经典气泡、角色比例、按压反馈及吸附翻转。参考提交：`5247dd6813d6e4430728f39ccc63d43cda046022`。原声明式示例保持独立，可同时安装；两者账本和设置互不共享。

使用包含 iframe 浮层支持的 OpenFic 安装本目录的插件包，在插件配置中填写 DeepSeek API Key 并启用。点击小鲸鱼或气泡切换余额、今日观测消费和上一轮费用；拖动角色移动，靠近左、右、下边缘时吸附，吸附左侧会翻转。方向键可移动角色，菜单可调整大小、气泡和吸附，刷新余额、重置位置或校正当日观测消费。

菜单中的“测试弹窗”和“测试浮层”使用宿主弹层接口打开独立 iframe 内容，可以通过内容中的按钮或宿主关闭按钮关闭。

安装包位于 `examples/plugins/dist/deepseek-whale-iframe-1.0.0.zip`。在项目根目录重新打包：

```bash
uv run --project backend python examples/plugins/build_package.py examples/plugins/deepseek-whale-iframe examples/plugins/dist/deepseek-whale-iframe-1.0.0.zip
```

余额每 60 秒从 DeepSeek 官方接口刷新；失败时保留最近成功值。余额下降按账户、币种和北京时间日期累计为观测消费，增加额单独记录；该数字并非完整账单。上一轮费用来自 OpenFic 的 USD 用量事件，与余额币种分开显示。配置密钥只发送到 DeepSeek 官方接口，不发送给 iframe。

拖动期间的位置更新仅在浏览器中进行，松手后通过插件存储保存一次；外观与账本属于各自的插件数据。iframe 的交互区域是矩形，即使内部像素透明也会阻挡下层点击，区域外可以穿透。插件不实现上游的完整气泡编辑器、音效、其他厂商和 DSH 账户协议。

`assets/whale.png` 是上游 `assets/DSniang1.png` 的原始素材。上游代码按 MIT 许可，素材不属于 MIT 许可，仅按上游说明随插件原样提供；详见 [UPSTREAM-LICENSE](UPSTREAM-LICENSE) 和 [UPSTREAM-PROVENANCE.md](UPSTREAM-PROVENANCE.md)。
