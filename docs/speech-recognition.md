# 语音转写

在「设置 → 语音转写」选择并配置提供商，语音识别不设置独立启用开关。录音需要 HTTPS 或 localhost 以及麦克风权限。

助手输入框的麦克风按钮使用与工具栏一致的 26px 圆形 hover。进入语音模式时沿用原输入框的 10px 圆角与边框，通过简短的高度动画下移并压低至 44px，底部工具栏折叠隐藏，然后淡入语音内容。语音栏左侧是取消按钮，中间显示由麦克风实际音量驱动的实时波形，右侧是停止和发送按钮。系统设置减少动态效果时直接切换。

- 停止：结束录音并转写，将文字追加到原有草稿，恢复文字输入框，不发送消息。
- 发送：结束录音并转写，将原有草稿与转写文字一同交给现有消息发送流程；转写文字不会先写入输入框。附件和已有的发送检查仍沿用原有流程。
- 转写期间显示识别状态，阻止重复提交，可取消；录音期间可按 Escape 取消。取消、切换任务或离开项目都会回收麦克风和音频分析资源，并取消未完成的转写。
- 左侧取消按钮在录音、转写、错误状态均可用；取消后保留原草稿、恢复工具栏且不聚焦输入框，不触发识别或发送。
- 识别失败或未检测到语音时保留录音，不发送消息。可以再次选择停止以重试填入文字，或选择发送以重试提交。

语音功能仅在 Agent 输入框提供，不提供音频文件选择入口。

录音最长 5 分钟，音频最大 30 MB。浏览器将其解码并转换为 16 kHz、单声道、16-bit PCM WAV。后端再次检查格式、时长、完整性和大小。所有提供商共用每个后端进程一个识别任务的限额，超出返回 429；识别超时为 180 秒。关闭窗口会中止浏览器请求，并通过请求 ID 显式取消后端任务，本地子进程会被终止并回收。

## 本地模型

在 backend 目录安装后端依赖：

```sh
uv sync
```

ASR 原生运行库是后端默认依赖，无需额外安装。SenseVoice 模型文件仍按需下载，不随后端安装或启动自动下载。

### SenseVoice Small

默认使用 CPU 和 INT8 ONNX 模型。点击「准备模型」显式下载固定版本的模型、词表和 Silero VAD（约 241 MB）；资源保存在 `OPENFIC_DATA_DIR/asr/sensevoice`。下载先写临时文件，通过大小和 SHA-256 检查后原子替换，重试会复用已校验的文件。普通转写、启动应用、切换提供商不会触发下载。

后端内部自动在 Hugging Face 和 hf-mirror 之间选源，设置页不提供下载源选项。下载时并发发送有时限的 HEAD 探测，优先使用最先成功响应的源；下载或完整性校验失败后切换备用源。探测全部失败时仍按 Hugging Face、hf-mirror 的顺序尝试下载，以兼容不支持 HEAD 的源。所有源使用相同固定版本路径、文件大小和 SHA-256。

设置页中的本地模型说明为「SenseVoice Small · INT8」。尚未准备模型时提供「准备模型」按钮，下载时显示当前文件、下载源、已下载 / 总大小和进度条；校验完成后隐藏按钮和进度区域，仅显示加粗的「已就绪」徽标。重新进入设置页会重新加载配置、模型状态和准备状态，期间显示统一 loading；已存在完整本地模型时不显示历史进度，正在下载时继续显示实时进度。失败后可重试并复用已经校验的文件。

本地提供商显示为「Sense Voice (本地)」，使用 thesvg 的 Qwen 图标。所有选择器和文本输入框的宽度统一为 192px，以完整显示本地提供商名称。

可以分别配置模型、词表、VAD 的绝对路径以离线运行，支持自备 FP32 模型。自定义文件由部署者维护；管理缓存中的文件会校验哈希。支持 `auto`、`zh`、`en`、`yue`、`ja`、`ko`。独立 Python 子进程按需加载模型，以 Silero VAD 切分语音并恢复首段起始处的少量音频；结束、错误、超时或取消后回收进程。每条录音重新加载模型，以限制常驻内存。

## 云端提供商

各提供商配置分别保存，切换不会删除其他提供商的密钥。API Key 使用项目现有 Fernet 加密服务保存，不在配置响应中返回。未修改密钥输入框时保留原值；修改后清空并保存会删除密钥。

| 提供商 | 默认模型 | 请求方式 |
| --- | --- | --- |
| OpenAI / 兼容服务 | `whisper-1` | `/audio/transcriptions` multipart |
| Groq | `whisper-large-v3-turbo` | OpenAI 兼容 multipart |
| Mistral | `voxtral-mini-latest` | `/audio/transcriptions` multipart |
| Deepgram | `nova-3` | `/listen`，WAV 请求体 |
| Azure Speech | Fast Transcription API | `/speechtotext/transcriptions:transcribe?api-version=2024-11-15` |

API 基础地址可覆盖默认值。OpenAI 兼容的本地服务可以不设置密钥。Azure 默认区域为 eastus，可修改为自己的区域地址；指定识别语言时使用 `zh-CN`、`en-US` 等完整区域代码。其他服务使用其支持的语言代码，`auto` 表示省略语言提示或自动识别。

云端识别会将音频发送给所选服务；不会自动回退到其他提供商。转写请求不会把原始音频保存为项目附件；HTTP 上传可能使用框架管理的临时文件，请求结束后关闭清理。识别结果只有在用户插入正文、笔记或助手草稿后才进入相应保存流程。

## API

- `GET /api/v1/audio/config`：读取设置，密钥只返回 `has_api_key`。
- `PUT /api/v1/audio/config`：保存当前提供商配置；`api_key` 省略或 null 保留，空字符串删除。
- `GET /api/v1/audio/local-status`：SenseVoice 资源校验状态。
- `POST /api/v1/audio/prepare`：显式准备 SenseVoice 资源，最多 600 秒。
- `GET /api/v1/audio/prepare/status`：读取准备状态、当前文件、下载源及已下载 / 总字节数。
- `POST /api/v1/audio/transcriptions`：multipart `file` 为规范 WAV，可选 `request_id` 为 UUID，返回 `text`、`provider`、`audio_seconds`。
- `DELETE /api/v1/audio/transcriptions/{request_id}`：幂等取消，等待任务释放资源。

以上接口沿用应用现有认证中间件。取消和并发状态由后端进程管理，多 worker 部署需将同一客户端的识别与取消请求，以及模型准备与进度请求路由到同一 worker。

## 测试

```sh
cd backend
uv run pytest tests/api/test_audio.py tests/api/test_asr_models.py -q
cd ../frontend
pnpm type-check
pnpm build
pnpm exec playwright install chromium
pnpm test:e2e:asr
```

独立 ASR E2E 配置会启动隔离数据目录的真实 FastAPI 后端、前端和本地 HTTP ASR 测试服务。覆盖配置持久化、提供商切换、内联录音与实时波形、停止回填、直接发送、保留草稿、无音频选择入口、错误重试、取消和未准备模型状态，以及桌面 / 手机布局和减少动态效果模式。直接发送测试通过真实会话创建与消息提交流程验证，最终消息接口使用测试响应，避免运行云端 LLM。模型下载进度 UI 测试使用受控的准备状态响应，覆盖实际字节百分比、校验前不显示完成、移动端和失败重试；Python 测试验证流式下载、探测、切源、完整性校验及进度接口。云端协议由后端测试和本地 HTTP 服务验证，不需要真实云端密钥或产生计费。

真实 SenseVoice E2E 可另外运行：先准备模型，再从 [固定版本测试音频](https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/2365baeacb507f821a0c8120fcee3d484dba7a07/test_wavs/en.wav) 下载英文样本，然后：

```sh
OPENFIC_ASR_MODEL_DIR=/path/to/sensevoice \
OPENFIC_ASR_SAMPLE=/path/to/en.wav \
pnpm test:e2e:asr
```

模型目录需包含 `model.int8.onnx`、`tokens.txt`、`silero_vad.onnx`。使用系统 Chromium 可设置 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`。未提供模型和样本时，仅真实模型 E2E 会跳过。

## 参考实现

- [DeepSeek Harness SenseVoice](https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/experimental/speech-to-text-sensevoice)：参考显式准备、固定资源身份、进程隔离、VAD 和起始音频补偿的设计。Python 推理与服务代码独立实现；`sensevoice-assets.json` 记录相同上游公开模型的版本和校验值。
- [OpenWebUI audio router](https://github.com/open-webui/open-webui/blob/main/backend/open_webui/routers/audio/__init__.py)：参考本地/云端提供商选择及各 ASR 协议，不复制其实现代码。
