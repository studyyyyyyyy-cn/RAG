# RAG Pro — 企业级知识库检索增强生成系统

**HNSW + BM25 + RRF 混合检索 × Neo4j 知识图谱 × 多智能体输出 × MCP 外部集成**

---

## 项目预览

| 智能问答 | 知识图谱 |
|:---:|:---:|
| ![问答](docs/images/1.png) | ![图谱](docs/images/2.png) |

---

## 环境准备

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 后端运行 |
| Node.js | 18+ | 前端构建 |
| Docker Desktop | 任意 | Neo4j 图数据库 |
| Git | 任意 | 代码管理 |

```bash
git clone https://github.com/studyyyyyyyy-cn/RAG.git && cd RAG

# 后端
cd backend && python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt

# 前端
cd ../frontend && npm install
```

> 国内用户可设置 `HF_ENDPOINT=https://hf-mirror.com` 加速模型下载

---

## 启动

双击项目根目录 `start.bat`，自动：清理旧进程 → 启动 Neo4j → 启动后端(8000) → 启动前端(5173)

或手动：

```bash
docker-compose up -d neo4j
cd backend && venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
cd frontend && npx vite --host 0.0.0.0
```

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:5173 |
| API 文档 | http://localhost:8000/docs |
| 知识图谱 | http://localhost:5173/knowledge-graph |
| 向量状态 | http://localhost:5173/vector-status |
| Neo4j | http://localhost:7474 |

---

## 整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                    Frontend (Vue 3 + Element Plus + ECharts)      │
│  Dashboard │ KB │ Chat │ Graph │ Vector │ Shortcuts │ Settings  │
└────────────────────────┬─────────────────────────────────────────┘
                         │ REST + SSE
┌────────────────────────┴─────────────────────────────────────────┐
│                    Backend (FastAPI + Uvicorn)                   │
│                                                                  │
│  API Layer              Core Engine              External        │
│  ─────────              ───────────              ────────        │
│  /kb CRUD               embedder.py             Milvus Lite      │
│  /documents             vector_store.py         Neo4j (Bolt)     │
│  /chat (SSE)            retriever.py            LiteLLM          │
│  /agent                 chunker.py              HuggingFace      │
│  /graph                 graph_store.py          hnswlib          │
│  /vector-status         graph_builder.py                         │
│  /llm/configs           llm_manager.py                           │
│  /mcp                   reranker.py                              │
│                                                                  │
│  Data Layer: SQLite (元数据) + Milvus (向量) + Neo4j (图谱)        │
└──────────────────────────────────────────────────────────────────┘
```

---

## 数据流

### 文档入库

```
上传 → DocumentParser(PyMuPDF/python-docx) → Chunker(9种策略)
    → BGE-M3 Embedding(dense 1024维 + sparse 词权重)
    → Milvus (HNSW索引) + SQLite (元数据)
    → LLM 实体抽取 → Neo4j (节点+边) → 图谱向量化 → Milvus kb_{id}_graph
```

### 问答检索

```
用户提问 → BGE-M3 嵌入 (1024维 dense + sparse)
  ├─→ 文档检索: HNSW ANN (余弦) + BM25 关键词 → RRF k=60 融合 → top-5
  └─→ 图谱检索: HNSW 搜 kb_{id}_graph → 最佳实体 → Neo4j 1-hop 邻居
  ↓
BGE-Reranker 精排 → Prompt 组装 → LLM 流式回答
```

### Prompt 结构

```
【匹配统计】文档chunk: 5条 | 图谱节点: 3个 | 图谱关系: 7条
【参考资料】
  [资料1] IBM年报.pdf - 第12页
  IBM operates across five business segments...
【知识图谱上下文】
  核心实体: IBM（组织，总部:美国）
  关联关系:
    IBM 研发 量子计算（概念）
    IBM 收购 Red Hat（组织）[时间:2018年]
---
用户问题: IBM的主要业务是什么？
```

---

## 项目结构

```
RAG-Pro/
├── backend/app/
│   ├── agents/              # 6 种智能体 (文本/图表/报表/网页/数据/图谱)
│   │   ├── base_agent.py    # Agent 基类 + 意图检测
│   │   ├── chart_agent.py   # ECharts 图表生成
│   │   ├── report_agent.py  # HTML 报表生成
│   │   ├── webpage_agent.py # 网页发布
│   │   ├── data_agent.py    # 数据分析 (表格+洞察)
│   │   └── graph_agent.py   # 知识图谱可视化
│   ├── api/v1/              # REST API 路由
│   │   ├── knowledge.py     # 知识库 CRUD + collection 修复
│   │   ├── document.py      # 文档上传/分块/嵌入 + 图谱自动构建
│   │   ├── chat.py          # 问答对话 + SSE 流式输出
│   │   ├── agent.py         # Agent 执行入口
│   │   ├── graph_api.py     # 图谱数据查询 API
│   │   ├── vector_status.py # 向量状态监控 + SSE 重载
│   │   ├── shortcut.py      # 快捷方式管理
│   │   └── llm_provider.py  # LLM 配置管理
│   ├── core/                # 核心引擎
│   │   ├── vector_store.py  # 向量存储 (Milvus/InMemory) + HNSW+BM25+RRF
│   │   ├── embedder.py      # Embedding 抽象层 (BGE-M3/MiniLM/OpenAI)
│   │   ├── retriever.py     # 检索流水线 (文档向量 + 图谱双路)
│   │   ├── reranker.py      # BGE-Reranker Cross-Encoder
│   │   ├── chunker.py       # 9 种分块策略 (递归/智能/QA/表格/书籍/论文...)
│   │   ├── document_parser.py    # PDF/DOCX/CSV/TXT/MD 解析
│   │   ├── llm_manager.py   # LiteLLM 多源 LLM 管理
│   │   ├── generator.py     # RAG 答案生成器
│   │   ├── agent_router.py  # 意图路由 → Agent 分发
│   │   ├── graph_store.py   # Neo4j 图数据库操作 (节点/边/遍历)
│   │   ├── graph_builder.py # 文档 → 实体抽取 → 图构建流水线
│   │   ├── entity_extractor.py  # LLM 实体关系抽取
│   │   ├── graph_retriever.py   # 图谱检索 + 向量融合
│   │   ├── graph_to_vector.py   # 图谱节点/边 → 自然语言 → Embedding
│   │   ├── confidence.py    # 置信度评估
│   │   └── exceptions.py    # 异常体系 (15+ 种类型)
│   ├── models/              # SQLAlchemy ORM 模型
│   └── mcp/                 # MCP 协议 (SSE + JSON-RPC)
├── frontend/src/
│   ├── views/               # 页面 (Dashboard/KnowledgeBase/Chat/Graph/Vector)
│   ├── components/          # ChatMessage/ChartRenderer/ReportViewer/SourceCitation
│   ├── api/index.js         # Axios API 封装
│   └── styles/theme.css     # 全局主题
├── docs/                    # 文档 (技术手册/快速入门/架构)
├── docker-compose.yml       # Neo4j + PostgreSQL + Redis + Milvus
└── start.bat                # 一键启动
```

---

## 功能详解

### 1. 文档解析

| 格式 | 解析库 | 方法 |
|------|--------|------|
| PDF | PyMuPDF (fitz) | 逐页 `get_text("text")` |
| DOCX | python-docx | 按段落读取，识别 Heading 为章节 |
| CSV | csv.DictReader | 每 20 行合成一页，附带表头 |
| TXT/MD | open | 双换行分段，约 2000 字/页 |

编码自动检测：`chardet` 检测 → 依次尝试 UTF-8/GBK/Big5/Latin-1

### 2. 文本分块 (9 种策略)

| 策略 | 适用场景 | 参数 |
|------|----------|------|
| **recursive** | 通用默认 | 512 token/块，64 重叠 |
| **intelligent** | 结构化文档 | 检测标题/段落层次 |
| **qa** | Q&A 对 | 识别 Q:/A:/问:/答: |
| **table** | CSV 数据 | 每行+表头 |
| **book** | 书籍 | 按章节标题 |
| **paper** | 论文 | 按摘要/方法/结论 |
| **resume** | 简历 | 按教育/工作/技能 |
| **general** | 固定大小 | 1536 字符/块 |
| **parent_child** | 高质量 | 子块512 + 父块1536 |

### 3. 向量嵌入

使用 **BAAI/bge-m3** (1024 维)，同时输出 dense（稠密向量）和 sparse（稀疏词权重）。

```
"今天天气真好" → [0.023, -0.451, 0.892, ...] (1024个float32)
                + {token_1234: 0.85, token_5678: 0.42} (词权重)
```

本地模型优先加载 (`backend/models/BAAI/bge-m3/`)，缓存复用避免重复加载。

### 4. 向量存储

双模架构，自动切换：

| 模式 | 持久化 | 索引 |
|------|--------|------|
| **Milvus Lite** | `milvus.db` 文件 | HNSW (M=16, ef=200, COSINE) |
| **InMemory** | `vectors.json` | Numpy 余弦相似度 |

每个知识库两个 Collection：`kb_{id}` (文档) + `kb_{id}_graph` (图谱)。

### 5. 混合检索

```
HNSW ANN (余弦距离) ─→ Dense top-60 ─┐
                                       ├─ RRF k=60 ─→ top-5
BM25 关键词 (sparse) ─→ Sparse top-60 ─┘
```

RRF (Reciprocal Rank Fusion) 不必担心两路分数量纲不同，只看排名：

```
RRF_score(d) = Σ 1/(60 + rank_i(d))   i ∈ {dense, sparse}
```

### 6. 知识图谱

| 步骤 | 技术 | 产出 |
|------|------|------|
| 实体抽取 | LLM (DeepSeek/OpenAI) + Prompt 模板 | JSON {entities, relations} |
| 图存储 | Neo4j (Cypher: MERGE) | Entity 节点 + RELATED_TO 边 |
| 向量化 | `node_to_text()` / `edge_to_text()` | 自然语言 → Embedding |
| 检索 | 独立搜 `kb_{id}_graph` → 最佳实体 → 1-hop | 图谱上下文文本 |

### 7. 多智能体

LLM 意图检测 → 路由到 6 种 Agent：

```
text → Markdown     chart → ECharts      report → HTML
webpage → URL       data_table → 表格     knowledge_graph → 力导向图
```

前端 `ChatMessage.vue` 按 `message.type` 分发渲染。

### 8. MCP 集成

符合 MCP 2024-11-05 协议，SSE + JSON-RPC 传输。提供 `list_knowledge_bases` 和 `rag_chat` 两个工具，Claude Desktop 等外部客户端可直接调用。

---

## 首次使用

1. **系统设置** → 添加 LLM（如 DeepSeek: `deepseek-chat`，API Key: `sk-xxx`）
2. **知识库** → 创建 → 上传文档 → 选分块策略 → 执行分块
3. **向量状态** → 点"重载"确认向量入库（绿色=正常，红色=需处理）
4. **知识图谱** → 点"重建图谱"（需要 LLM 已配置 + Neo4j 已启动）
5. **智能问答** → 选择知识库，输入问题

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [RAG-Pro 完整技术手册](docs/RAG-Pro完整技术手册.md) | 15 章节，从解析到 LLM 回答的完整管线详解 |
| [快速入门指南](docs/getting-started.md) | 环境安装 + 首次使用步骤 + 常见问题 |
| [MCP API 设计](docs/mcp-api-design.md) | MCP 协议接口设计文档 |

## License

MIT
