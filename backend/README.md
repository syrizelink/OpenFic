# OpenFic
<p>
  <img src="https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/react-19-149ECA?style=flat-square&logo=react&logoColor=white" alt="React 19">
  <img src="https://img.shields.io/badge/fastapi-0.127%2B-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
</p>


**OpenFic** 是AI Agent时代专为小说创作打造的一站式写作平台，构建设定、设计角色、定制工作流，让Agent适应你的写作流程，而非反之。与OpenFic一起，将你的脑海中的世界变为现实。

## 特性

- 🚀开箱即用：使用Docker或pip快速安装，无需复杂配置
- 🤝全面的模型支持：无缝集成来自数十家提供商的模型，或是任何兼容OpenAI API的模型
- 📱响应式UI：在桌面端、移动端和浏览器上享受无缝的流畅体验
- 🧩定制化工作流：高度可配置的Agent系统，自由的修改任何Prompt，构建属于你的工作流
- ✒️以写作为中心：与Agent深度集成的辅助创作，发散思维、构建情节、协同编辑，告别抽卡式的一键生成
- 💾本地持久化：所有项目数据保存在本地，零云存储依赖
- 🧠语义化检索：基于向量的Agentic RAG，让Agent能够在百万字级别的项目中高效检索过往信息
- ⚖️成本优先的上下文管理：智能压缩、动态截断、稳定缓存，尽可能降低使用成本


## 安装

### 🐳 Docker（推荐）

如果使用容器方式安装进行自托管是推荐的安装方式。

#### 1. 拉取镜像

```bash
docker pull ghcr.io/syrizelink/openfic:latest
```

#### 2. 运行容器

```bash
docker run -d -p 8000:8000 -v "openfic:/data" --name openfic ghcr.io/syrizelink/openfic:latest
```

#### 3. 启动后访问

```text
http://localhost:8000
```

### 🐍 Python pip

在开始安装前，确保你已经安装了Python3.12+

#### 1. 安装OpenFic

```bash
pip install openfic
```

#### 2. 启动服务

```bash
openfic serve
```

#### 3. 启动后访问

```text
http://localhost:8000
```

### 桌面应用

前往 <https://github.com/syrizelink/OpenFic/releases> 下载桌面应用，在你的系统上原生运行，而无需额外步骤。