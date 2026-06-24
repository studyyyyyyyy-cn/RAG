# 快速入门指南

## 一、环境准备

| 组件 | 最低版本 | 检查命令 | 说明 |
|------|----------|----------|------|
| Python | 3.10+ | `python --version` | 后端运行环境 |
| Node.js | 18+ | `node --version` | 前端构建 |
| npm | 9+ | `npm --version` | 包管理 |
| Docker Desktop | 任意 | `docker --version` | Neo4j 图数据库（可选） |
| Git | 任意 | `git --version` | 代码管理 |

## 二、安装

```bash
# 1. 克隆项目
git clone https://github.com/studyyyyyyyy-cn/RAG.git
cd RAG

# 2. 后端虚拟环境
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt
# 关键依赖: fastapi, pymilvus, FlagEmbedding, litellm, neo4j, hnswlib

# 4. 前端
cd ../frontend
npm install
```

### 模型下载

项目默认使用 `BAAI/bge-m3` (~4.3GB) 作为 Embedding 模型，`BAAI/bge-reranker-v2-m3` 作为 Reranker。

首次启动时自动从 HuggingFace 下载到 `backend/models/`。国内用户可设置镜像加速：

```bash
# Windows
set HF_ENDPOINT=https://hf-mirror.com
# Mac/Linux
export HF_ENDPOINT=https://hf-mirror.com
```

## 三、启动

### Windows 一键启动

双击项目根目录 `start.bat`，自动：
1. 杀掉旧 Python 进程，清理 Milvus 锁文件
2. 检查并安装前端依赖
3. 启动 Neo4j（Docker，如果已安装）
4. 启动后端 API (端口 8000，支持热重载)
5. 启动前端 Vite 开发服务器 (端口 5173)

### 手动启动

```bash
# 终端 1: Neo4j（可选，知识图谱功能需要）
docker-compose up -d neo4j

# 终端 2: 后端
cd backend
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 终端 3: 前端
cd frontend
npx vite --host 0.0.0.0
```

### 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端主页 | http://localhost:5173 | Vue 3 应用 |
| 智能问答 | http://localhost:5173/chat | 核心功能 |
| 知识图谱 | http://localhost:5173/knowledge-graph | 力导向图 |
| 向量状态 | http://localhost:5173/vector-status | 向量监控 |
| API 文档 | http://localhost:8000/docs | Swagger UI |
| 健康检查 | http://localhost:8000/health | `{"status":"ok"}` |
| Neo4j 控制台 | http://localhost:7474 | 用户名 neo4j / 密码 password |

## 四、首次使用流程

### 步骤 1: 配置 LLM

进入 `系统设置` 页面，添加 LLM 模型配置：

| 字段 | 示例值 | 说明 |
|------|--------|------|
| provider | deepseek | 提供商 |
| model_name | deepseek-chat | 模型名 |
| display_name | DeepSeek V4 | 显示名 |
| api_key | sk-xxx | API 密钥 |
| base_url | https://api.deepseek.com | API 地址（可选） |

支持: OpenAI / Anthropic / DeepSeek / Ollama / 智谱 / 通义千问 / vLLM / 自定义代理

> 点击"测试连接"确认配置正确后再保存。

### 步骤 2: 创建知识库

进入 `知识库` 页面，点击"创建知识库"：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 名称 | - | 必填 |
| 描述 | - | 可选 |
| Embedding 模型 | BAAI/bge-m3 | 推荐默认 |
| chunk_size | 512 | token 数 |
| chunk_overlap | 64 | 重叠 token 数 |

### 步骤 3: 上传文档

进入知识库的文档管理页，上传文件。支持格式: PDF / DOCX / CSV / TXT / MD（最大 100MB）。

上传后系统自动解析文档内容。状态变化: `pending → parsing → parsed`

### 步骤 4: 执行分块

文档解析完成后，选择分块策略并执行分块：

| 策略 | 适用场景 |
|------|----------|
| recursive | 通用，逐级分隔符切割 |
| intelligent | 按标题/段落结构智能分块 |
| qa | Q&A 格式文档 |
| table | CSV/表格数据 |
| book | 书籍章节 |
| paper | 学术论文 |
| parent_child | 子块检索 + 父块上下文 |
| general | 固定大小分块 |

状态变化: `parsed → chunking → done`

### 步骤 5: 构建知识图谱（可选）

分块完成后，进入 `知识图谱` 页面，选择知识库，点击 **重建图谱**。

系统自动:
1. 用 LLM 从每个 chunk 提取实体和关系
2. 写入 Neo4j 图数据库
3. 将节点和边转为自然语言文本 → Embedding → 存入向量库

### 步骤 6: 验证向量入库

进入 `向量状态` 页面，确认每个知识库的向量数据已入库。红色标记表示需要重载。

### 步骤 7: 开始问答

进入 `智能问答` 页面，选择知识库，输入问题。系统自动:
1. 检索最相关的文档 chunk
2. 匹配知识图谱实体
3. 融合上下文生成回答

## 五、页面导航

| 页面 | 路由 | 功能 |
|------|------|------|
| 数据看板 | /dashboard | KB 统计、对话趋势 |
| 知识库管理 | /knowledge | 创建/编辑/删除 KB |
| 文档管理 | /knowledge/:id/documents | 上传/分块/查看状态 |
| 智能问答 | /chat | RAG 对话 + 多智能体 |
| 知识图谱 | /knowledge-graph | 力导向图浏览 + 重建 |
| 向量状态 | /vector-status | 向量数量监控 + 重载 |
| 快捷方式 | /shortcuts | 收藏问答结果 |
| 系统设置 | /settings | LLM 配置管理 |
| MCP 测试 | /mcp-test | MCP 协议调试 |
| API 测试 | /api-test | 接口调试 |

## 六、常见问题

### 1. 分块报维度不匹配

Milvus collection 维度与 Embedder 输出不一致。解决方法：

```bash
# 对出问题的 KB 调用修复接口
curl -X POST http://localhost:8000/api/v1/kb/{kb_id}/repair-collection
```

或在 `向量状态` 页点"重载"自动修复。

### 2. Milvus 报 function_score 错误

Milvus Lite 的 gRPC 解析器 bug。v2.1 已绕过，改用本地 numpy/HNSW 检索。确保代码已更新到最新版本。

### 3. 知识图谱无法显示

确认 Neo4j 已启动且后端能连接：
```bash
docker ps | grep neo4j   # 检查容器是否运行
pip list | grep neo4j    # 检查 Python 驱动是否安装
```

### 4. 前端白屏

确认 Vite 开发服务器正常运行，前端端口 5173 未被占用，浏览器控制台无报错。
