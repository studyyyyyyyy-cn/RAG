# RAG 知识库系统 - 快速启动指南

## 环境要求

- **Docker** >= 20.10 & **Docker Compose** >= 2.0
- **Python** >= 3.11
- **Node.js** >= 18
- **GPU** (可选): 如需本地运行 Embedding/Reranker 模型，建议 NVIDIA GPU + CUDA

---

## 一、Docker Compose 启动基础设施

项目依赖 PostgreSQL、Milvus、Redis 三个基础服务，通过 Docker Compose 一键启动：

```bash
# 进入项目根目录
cd RAGAPP

# 启动基础设施 (PostgreSQL + Redis + Milvus)
docker-compose up -d postgres redis etcd minio milvus
```

等待所有服务启动完成，可用以下命令检查状态：

```bash
docker-compose ps
```

确认以下服务均为 `healthy` 或 `running`：

| 服务 | 端口 | 用途 |
|------|------|------|
| postgres | 5432 | 元数据存储 |
| redis | 6379 | 缓存 + 任务队列 |
| milvus | 19530 | 向量数据库 |
| minio | 9001 | Milvus 对象存储 |
| etcd | 2379 | Milvus 元数据 |

---

## 二、启动后端

### 方式 A: 本地开发运行

```bash
# 进入后端目录
cd backend

# 创建 Python 虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动 FastAPI 开发服务器
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

后端启动后访问 http://localhost:8000/health 验证，应返回：
```json
{"status": "ok", "version": "1.0.0"}
```

API 文档自动生成：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 方式 B: Docker 启动

```bash
docker-compose up -d backend
```

### 启动 Celery Worker (异步文档处理)

```bash
# 在后端目录下，新开一个终端
cd backend
celery -A app.core.celery_app worker --loglevel=info
```

或使用 Docker:
```bash
docker-compose up -d celery-worker
```

---

## 三、启动前端

### 方式 A: 本地开发运行

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端启动后访问 http://localhost:3000

Vite 开发服务器已配置 `/api` 代理到后端 `http://localhost:8000`，无需额外配置。

### 方式 B: Docker 启动

```bash
docker-compose up -d frontend
```

访问 http://localhost:3000

---

## 四、一键全部启动

如果想一次性启动所有服务（基础设施 + 后端 + 前端 + Celery）：

```bash
docker-compose up -d
```

全部服务端口清单：

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | http://localhost:3000 | Vue3 应用 |
| 后端 API | http://localhost:8000 | FastAPI |
| API 文档 | http://localhost:8000/docs | Swagger UI |
| Milvus | localhost:19530 | 向量数据库 |
| PostgreSQL | localhost:5432 | 关系数据库 |
| Redis | localhost:6379 | 缓存 |
| MinIO 控制台 | http://localhost:9001 | 对象存储管理 |

---

## 五、首次使用流程

### 1. 配置 LLM 模型

打开前端 → 进入「系统设置」页面 → 添加 LLM 模型配置：

**示例 - 添加 OpenAI:**
- 提供商: `openai`
- 模型名: `gpt-4o`
- API Key: `sk-xxxx`
- 设为默认: 是

**示例 - 添加本地 Ollama:**
- 提供商: `ollama`
- 模型名: `qwen2.5:7b`
- Base URL: `http://localhost:11434`
- API Key: 留空

点击「测试连接」验证配置正确后保存。

### 2. 创建知识库

进入「知识库管理」→ 点击「新建知识库」：
- 输入名称和描述
- 选择 Embedding 模型（默认 BGE-M3）
- 设置分块大小（默认 512 tokens）

### 3. 上传文档

点击知识库卡片的「文档」按钮 → 上传文件：
- 支持格式: PDF、Word (.docx)、CSV、TXT、Markdown (.md)
- 支持批量上传
- 上传后自动解析 → 分块 → Embedding → 向量化存储

### 4. 开始问答

进入「智能问答」页面：
- 选择知识库
- 输入问题，Enter 发送
- 支持 SSE 流式实时输出
- 每个回答附带来源引用和置信度评分

### 5. 使用智能体

在问答输入框旁点击「智能体」按钮：
- **生成图表**: 自动将知识库数据转为 ECharts 图表
- **生成报表**: 输出结构化 HTML 报表
- **数据分析**: 输出表格 + 图表 + 洞察

### 6. 保存快捷方式

在任意回答下方点击「保存快捷方式」→ 在「快捷方式」面板快速查看历史结果。

---

## 六、环境变量配置

后端配置文件: `backend/.env`

```bash
# 数据库
DATABASE_URL=postgresql+asyncpg://raguser:ragpass@localhost:5432/ragdb

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Milvus
MILVUS_HOST=localhost
MILVUS_PORT=19530

# Embedding 模型
DEFAULT_EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DEVICE=cpu           # 改为 cuda 启用 GPU 加速

# 检索参数
RETRIEVAL_TOP_K=20             # 混合检索候选数
RERANK_TOP_N=5                 # 重排序后保留数
CONFIDENCE_THRESHOLD=0.3       # 置信度阈值

# 分块参数
DEFAULT_CHUNK_SIZE=512
DEFAULT_CHUNK_OVERLAP=64

# 安全 (生产环境必须修改!)
SECRET_KEY=change-this-to-a-secure-random-string

# 调试
DEBUG=true
```

---

## 七、常见问题

### Milvus 启动失败
确保 Docker 分配了足够内存（建议 >= 4GB），etcd 和 minio 需要先于 milvus 启动。

### Embedding 模型下载慢
BGE-M3 模型首次加载会从 HuggingFace 下载（约 2GB）。可以：
- 设置 HuggingFace 镜像: `export HF_ENDPOINT=https://hf-mirror.com`
- 手动下载模型放到 `~/.cache/huggingface/` 目录

### GPU 加速
修改 `.env` 中 `EMBEDDING_DEVICE=cuda`，并确保安装了对应版本的 PyTorch CUDA。

### 端口冲突
如果默认端口被占用，修改 `docker-compose.yml` 中对应服务的 ports 映射。
