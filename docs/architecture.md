# 系统架构

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                   Frontend (Vue 3 + Element Plus)           │
│  Dashboard │ KB │ Chat │ Graph │ Vector │ Shortcuts │ Settings │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST API / SSE
┌──────────────────────┴──────────────────────────────────────┐
│                   Backend (FastAPI)                         │
│                                                             │
│  API Layer              Core Engine         External        │
│  ─────────              ───────────         ────────        │
│  /kb CRUD               embedder.py        Milvus Lite      │
│  /documents             vector_store.py    Neo4j            │
│  /chat (SSE)            retriever.py       LiteLLM          │
│  /agent                 chunker.py         HuggingFace      │
│  /graph                 graph_store.py                     │
│  /vector-status         graph_builder.py                   │
│  /llm/configs           llm_manager.py                     │
│  /mcp                   reranker.py                        │
│                                                             │
│  Data: SQLite + Milvus + Neo4j                             │
└─────────────────────────────────────────────────────────────┘
```

## 数据流

### 文档入库

```
Upload → DocumentParser → Chunker → Embedder → VectorStore + SQLite
                                              → EntityExtractor → Neo4j
```

### 问答检索

```
Query → Embedder → [HNSW+BM25+RRF] + [Graph Search] → Reranker → LLM
```

### 图构建

```
Chunks → LLM Entity Extraction → Neo4j Nodes/Edges → Graph-to-Vector
```

## 存储层

| 存储 | 用途 | 格式 |
|------|------|------|
| SQLite | 文档/Chunk/会话/配置元数据 | 结构化 |
| Milvus Lite | 1024维向量 | HNSW索引 |
| Neo4j | 知识图谱 | 图数据库 |

## Agent 路由

```
detect_intent(query) → text/chart/report/webpage/data_table/knowledge_graph
                            ↓
                    Agent.execute(query, context, llm_config)
                            ↓
                    {type, content: {...}}
```
