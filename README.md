# RAG-Pro

RAG-Pro 是一个本地优先的 RAG 知识库系统，提供知识库管理、文档上传与分块、混合检索、测试问答、流式对话和多种智能输出能力。项目采用前后端分离架构，前端基于 Vue 3，后端基于 FastAPI，默认可直接使用 SQLite 和 Milvus Lite 在本机运行。

## 功能简介

- 知识库管理：创建、编辑、删除知识库，配置 Embedding 模型、分块大小和重叠参数。
- 文档管理：支持批量上传和删除文档，查看解析状态、分块进度和错误信息。
- 多格式文档支持：支持 `pdf`、`csv`、`txt`、`md`、`docx`、`doc`。
- 文档分块：支持多种分块方式，包括普通分块和父子分块。
- 混合检索：基于 `BAAI/bge-m3` 实现稠密向量与稀疏向量检索。
- 问答重排：结合 `BAAI/bge-reranker-v2-m3` 对召回结果进行排序优化。
- RAG 对话：支持基于知识库的流式问答和多轮会话管理。
- 测试问答：提供独立的测试问答页，便于查看检索结果、上下文和生成效果。
- 智能输出：支持图表、报表、网页等不同回答形态的智能路由。
- LLM 配置管理：支持 OpenAI、Anthropic、DeepSeek、Ollama 及 OpenAI 兼容接口。
- MCP 接口：内置 `/mcp` 路由，方便扩展工具调用能力。

## 技术栈

- 前端：Vue 3、Vite、Element Plus、Pinia、Vue Router、ECharts
- 后端：FastAPI、SQLAlchemy、Uvicorn、Pydantic
- 数据库：SQLite（默认本地开发）、PostgreSQL（可选生产部署）
- 向量库：Milvus Lite（默认本地开发）、Milvus（Docker 部署）
- Embedding：`BAAI/bge-m3`
- Reranker：`BAAI/bge-reranker-v2-m3`
- LLM 网关：LiteLLM

## 项目结构

```text
RAG-Pro/
├─ backend/                # FastAPI 后端
│  ├─ app/                 # API、核心逻辑、数据模型
│  ├─ data/                # SQLite、Milvus Lite 本地数据
│  ├─ models/              # 本地模型目录
│  ├─ uploads/             # 上传文件目录
│  ├─ requirements.txt
│  └─ start_backend.py
├─ frontend/               # Vue 3 前端
│  ├─ src/
│  ├─ package.json
│  └─ vite.config.js
├─ docs/                   # 设计与使用文档
├─ sample-data/            # 示例数据
├─ install.bat             # Windows 一键安装
├─ start.bat               # Windows 一键启动前后端
└─ docker-compose.yml      # Docker 编排文件
```

## 运行环境

### 本地开发

- Python 3.10 及以上
- Node.js 18 及以上
- npm 9 及以上
- Windows 推荐直接使用仓库内的 `install.bat` 和 `start.bat`

### 可选 Docker 环境

- Docker 20.10 及以上
- Docker Compose 2.x

## 安装与运行

### 方式一：Windows 一键安装与启动

适合当前仓库默认开发方式。

1. 在项目根目录执行安装脚本：

```bat
install.bat
```

安装脚本会自动完成以下工作：

- 检查 Python、Node.js、npm
- 创建 `backend\venv` 虚拟环境
- 安装后端依赖
- 创建运行目录
- 安装前端依赖

2. 安装完成后执行启动脚本：

```bat
start.bat
```

启动后默认地址：

- 前端：`http://localhost:3000`
- 后端：`http://localhost:8000`
- Swagger 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

### 方式二：本地手动启动

#### 1. 启动后端

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

后端默认使用：

- SQLite：`backend/data/ragapp.db`
- Milvus Lite：`backend/data/milvus.db`

#### 2. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

前端 Vite 默认运行在 `3000` 端口，并将 `/api` 请求代理到 `http://localhost:8000`。

### 方式三：Docker 部署

如果你希望使用 PostgreSQL、Redis、Milvus 等完整基础设施，可以使用 Docker。

```bash
docker-compose up -d
```

默认服务：

- `frontend`：`http://localhost:3000`
- `backend`：`http://localhost:8000`
- `postgres`：`localhost:5432`
- `redis`：`localhost:6379`
- `milvus`：`localhost:19530`
- `minio`：`http://localhost:9001`

说明：

- `docker-compose.yml` 中的后端依赖了 `backend/Dockerfile`，如需 Docker 运行，请确认该文件存在并可正常构建。
- 当前项目本地开发默认并不依赖 PostgreSQL 和 Redis，可先使用本地模式验证功能。

## 首次使用流程

### 1. 配置 LLM

进入前端 `设置` 页面，添加一个可用模型配置。

常见示例：

- OpenAI
  - `provider`: `openai`
  - `model_name`: `gpt-4o`
  - `api_key`: 你的 API Key
- Ollama
  - `provider`: `ollama`
  - `model_name`: `qwen2.5:7b`
  - `base_url`: `http://localhost:11434`

后端接口：

- `POST /api/v1/llm/configs`
- `POST /api/v1/llm/configs/test`

### 2. 创建知识库

进入 `知识库` 页面，创建知识库并设置：

- 名称与描述
- Embedding 模型
- `chunk_size`
- `chunk_overlap`

后端接口：

- `POST /api/v1/kb`
- `GET /api/v1/kb`

### 3. 上传文档

进入某个知识库的文档页，上传文档。系统会先完成解析，再进入分块阶段。

后端接口：

- `POST /api/v1/kb/{kb_id}/documents`
- `GET /api/v1/kb/{kb_id}/documents`
- `GET /api/v1/kb/{kb_id}/documents/{doc_id}/status`

### 4. 执行分块

文档解析成功后，可对单个文档或批量文档执行分块。

后端接口：

- `POST /api/v1/kb/{kb_id}/documents/{doc_id}/chunk`
- `POST /api/v1/kb/{kb_id}/documents/chunk-batch`

### 5. 开始问答

进入 `聊天` 页面进行知识库问答，支持流式 SSE 返回和多轮会话。

后端接口：

- `POST /api/v1/chat`
- `GET /api/v1/conversations`
- `GET /api/v1/conversations/{conversation_id}`

### 6. 使用测试问答

项目包含单独的测试问答页面：`/kb/:id/test-chat`，适合调试检索与回答效果。

后端接口：

- `POST /api/v1/kb/{kb_id}/test-chat`

## 核心页面

- `/knowledge`：知识库管理
- `/knowledge/:id/documents`：文档管理
- `/kb/:id/test-chat`：测试问答
- `/chat`：正式问答
- `/shortcuts`：快捷结果
- `/dashboard`：数据看板
- `/settings`：模型与系统设置
- `/mcp-test`：MCP 测试
- `/api-test`：API 调试

## 关键配置

后端配置位于 `backend/app/config.py`，也支持通过 `backend/.env` 覆盖。

常用配置项：

```env
APP_NAME=RAG Knowledge Base
APP_VERSION=1.0.0
API_PREFIX=/api/v1

HOST=0.0.0.0
PORT=8000

DATABASE_URL=sqlite+aiosqlite:///backend/data/ragapp.db
REDIS_URL=redis://localhost:6379/0

MILVUS_URI=backend/data/milvus.db
MILVUS_HOST=localhost
MILVUS_PORT=19530

UPLOAD_DIR=backend/uploads
MAX_UPLOAD_SIZE_MB=100

DEFAULT_EMBEDDING_MODEL=BAAI/bge-m3
DEFAULT_RERANKER_MODEL=BAAI/bge-reranker-v2-m3
EMBEDDING_DEVICE=cpu

RETRIEVAL_TOP_K=20
RERANK_TOP_N=5
CONFIDENCE_THRESHOLD=0.3

DEFAULT_CHUNK_SIZE=512
DEFAULT_CHUNK_OVERLAP=64
PARENT_CHUNK_SIZE=1536

SECRET_KEY=change-this-to-a-secure-random-string
DEBUG=false
```

说明：

- 本地开发默认使用 SQLite 和 Milvus Lite，无需额外数据库服务。
- `EMBEDDING_DEVICE=cpu` 适合默认本地运行；如有 CUDA 环境，可改为 `cuda`。
- 项目会将 Hugging Face 模型缓存目录指向 `backend/models`。

## 常用接口

### 健康检查

- `GET /health`

### 知识库

- `GET /api/v1/kb`
- `POST /api/v1/kb`
- `GET /api/v1/kb/{kb_id}`
- `PUT /api/v1/kb/{kb_id}`
- `DELETE /api/v1/kb/{kb_id}`

### 文档

- `GET /api/v1/kb/{kb_id}/documents`
- `POST /api/v1/kb/{kb_id}/documents`
- `POST /api/v1/kb/{kb_id}/documents/{doc_id}/chunk`
- `POST /api/v1/kb/{kb_id}/documents/chunk-batch`
- `GET /api/v1/kb/{kb_id}/documents/{doc_id}/chunks`
- `DELETE /api/v1/kb/{kb_id}/documents/{doc_id}`

### 问答与会话

- `POST /api/v1/chat`
- `GET /api/v1/conversations`
- `GET /api/v1/conversations/{conversation_id}`
- `PUT /api/v1/conversations/{conversation_id}`
- `DELETE /api/v1/conversations/{conversation_id}`

### 模型配置

- `GET /api/v1/llm/configs`
- `POST /api/v1/llm/configs`
- `PUT /api/v1/llm/configs/{config_id}`
- `DELETE /api/v1/llm/configs/{config_id}`
- `POST /api/v1/llm/configs/test`

## 常见问题

### 1. 前端能打开，但无法问答

通常是以下原因之一：

- 后端未启动
- 尚未在 `设置` 页面配置可用 LLM
- 向量模型首次加载较慢，仍在初始化

建议先检查：

- `http://localhost:8000/health`
- `http://localhost:8000/docs`

### 2. 文档上传成功，但分块失败

建议检查：

- 文件格式是否受支持
- 文件内容是否可正常解析
- `backend/uploads` 是否有写入权限
- 模型是否已正确加载

### 3. 首次启动很慢

首次运行通常会下载或加载本地模型，尤其是：

- `BAAI/bge-m3`
- `BAAI/bge-reranker-v2-m3`

这属于正常现象。

### 4. Docker 模式启动失败

请重点确认：

- Docker Desktop 已启动
- 端口 `3000`、`8000`、`5432`、`6379`、`19530` 未被占用
- `backend/Dockerfile`、`frontend/Dockerfile` 可正常构建

## 补充说明

- 当前仓库已包含 `frontend/node_modules`、`backend/venv`、本地模型和测试数据；如果仅用于开发验证，可以直接利用现有环境。
- `docs/` 目录下还有架构设计、混合检索、分块优化等补充文档，适合进一步阅读。

## License

如需开源发布，请在此补充许可证信息。
