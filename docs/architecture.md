# 系统架构设计说明书

## 一、整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                    前端 Frontend (Vue 3 + Element Plus)           │
│                                                                    │
│  Dashboard  │  KnowledgeBase  │  Chat  │  KnowledgeGraph          │
│  VectorStatus │  Shortcuts  │  Settings  │  MCP/ApiTest          │
│                                                                    │
│  状态管理: Pinia (chat store + knowledge store)                   │
│  图表渲染: ECharts 5 (Bar/Line/Pie/Graph/Tree)                   │
│  SSE 流式: fetchEventSource                                      │
└────────────────────────┬─────────────────────────────────────────┘
                         │ REST API + SSE (localhost:8000)
┌────────────────────────┴─────────────────────────────────────────┐
│                    后端 Backend (FastAPI + Uvicorn)               │
│                                                                    │
│  ┌─────────────┐  ┌──────────────────┐  ┌──────────────────┐    │
│  │  API Layer  │  │   Core Engine    │  │   External       │    │
│  ├─────────────┤  ├──────────────────┤  ├──────────────────┤    │
│  │ /kb CRUD    │  │ embedder.py      │  │ Milvus Lite      │    │
│  │ /documents  │  │ vector_store.py  │  │ Neo4j (Bolt)     │    │
│  │ /chat (SSE) │  │ retriever.py     │  │ LiteLLM Gateway  │    │
│  │ /agent      │  │ reranker.py      │  │ HuggingFace Hub  │    │
│  │ /graph      │  │ chunker.py       │  │ BGE-M3 Model     │    │
│  │ /vector     │  │ graph_store.py   │  │ BGE-Reranker     │    │
│  │ /llm        │  │ graph_builder.py │  │ hnswlib          │    │
│  │ /mcp        │  │ llm_manager.py   │  └──────────────────┘    │
│  │ /shortcuts  │  │ generator.py     │                           │
│  └─────────────┘  │ agent_router.py  │                           │
│                    │ exceptions.py    │                           │
│                    └──────────────────┘                           │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                      Data Layer                             │ │
│  │  SQLite (ragapp.db)    Milvus Lite (milvus.db)   Neo4j      │ │
│  │  - knowledge_bases     - kb_{id} (1024维)       - Entity    │ │
│  │  - documents           - kb_{id}_graph (图谱)    - Chunk    │ │
│  │  - chunks              - HNSW 索引              - RELATION  │ │
│  │  - conversations       - sparse vector 字段                  │ │
│  │  - messages                                                │ │
│  │  - llm_configs                                              │ │
│  │  - shortcuts                                                │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

## 二、数据流详解

### 2.1 文档入库流程

```
1. 上传 PDF/DOCX/CSV/TXT/MD
      ↓
2. DocumentParser 解析
   - PDF → PyMuPDF (fitz) 逐页提取
   - DOCX → python-docx 按标题分节
   - CSV → csv.DictReader → 批量行
   - TXT/MD → 自然段落分割
      ↓
3. Chunker 分块 (9种策略可选)
   - recursive: 递归按分隔符分割 + overlap
   - intelligent: 检测标题/段落结构
   - qa: Q&A 对提取
   - table: CSV/Markdown 表行
   - book/paper/resume: 按章节/关键词
   - parent_child: 子块(512 tokens) + 父块(1536 tokens)
      ↓
4. BGE-M3 Embedding
   - dense: (n, 1024) float32 稠密向量
   - sparse: [{token_id: weight}, ...] 稀疏词权重
      ↓
5. 写入存储
   ├→ Milvus: dense_vector(1024维) + sparse_vector(JSON) + chunk_id + content
   └→ SQLite: chunk 元数据 (page/section/tokens/keywords/questions)
      ↓
6. 知识图谱构建 (自动触发)
   ├→ LLM 实体抽取 (entity_extractor.py)
   │   Prompt: EXTRACTION_SYSTEM → 输出 JSON {entities: [{name, type, aliases}], relations: [{source, target, relation}]}
   ├→ Neo4j 写入 (graph_store.py)
   │   - MERGE Entity nodes (id, name, entity_type, kb_id)
   │   - MERGE RELATED_TO edges (relation, weight)
   └→ 图谱向量化 (graph_to_vector.py)
       - 节点 → "IBM是一家组织，总部为美国。" → embedding → kb_{id}_graph
       - 边   → "IBM研发量子计算。" → embedding → kb_{id}_graph
```

### 2.2 问答检索流程

```
用户提问 "IBM的主要业务是什么？"
      ↓
1. BGE-M3 嵌入 → dense(1024维) + sparse({token: weight})
      ↓
2. 并行检索
   ├─ 文档检索 (vector_store.hybrid_search)
   │   ├→ HNSW ANN (余弦距离) → dense top-60
   │   ├→ BM25 关键词 (sparse vector 匹配) → sparse top-60
   │   └→ RRF k=60 融合 → top-5
   │
   └─ 图谱检索 (retriever._retrieve_graph_context)
       ├→ vector_store.search_graph() → kb_{id}_graph 搜索
       ├→ 最佳实体 → Neo4j get_neighbors(hops=1)
       └→ 构建上下文文本 (实体属性 + 邻居 + 关系)
      ↓
3. BGE-Reranker 精排 (Cross-Encoder)
   - 对 top-5 chunks 逐对打分 (query, chunk)
   - 按相关性重新排序
      ↓
4. Prompt 组装
   【匹配统计】文档chunk: 5条 | 图谱节点: 3个 | 图谱关系: 7条
   【参考资料】[资料1] IBM年报.pdf - 第12页\n...
   【知识图谱上下文】核心实体: IBM（组织，总部:美国）\n关联关系:\n  IBM 研发 量子计算...
   【置信度】85% (high)
   ↓
5. LiteLLM → DeepSeek/OpenAI/... → 流式返回
```

## 三、Agent 智能体架构

```
用户提问
  ↓
detect_intent(query) → LLM 意图识别
  ↓
┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────────┐
│  text    │  chart   │  report  │ webpage  │data_table│knowledge_graph│
│  文本     │  图表     │  报表    │  网页     │  数据     │  知识图谱     │
├──────────┼──────────┼──────────┼──────────┼──────────┼──────────────┤
│ RAG生成  │ ECharts  │ HTML片段 │ 发布页面  │ 表格+图表 │ 力导向图     │
│ Markdown │ JSON配置 │ 语义HTML │ 静态文件  │ +洞察    │ ECharts      │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────────────┘
  ↓
前端 ChatMessage.vue → v-if type 分发渲染
```

## 四、存储层设计

### 4.1 SQLite 表结构

| 表 | 关键字段 | 用途 |
|------|------|------|
| knowledge_bases | id, name, embedding_model, chunk_size | KB 配置 |
| documents | id, kb_id, filename, parse_status, chunk_method | 文档状态 |
| chunks | id, doc_id, content, chunk_index, parent_chunk_id | 分块数据 |
| conversations | id, kb_id, title | 对话会话 |
| messages | id, conversation_id, role, content(JSON), type, confidence | 消息记录 |
| llm_configs | id, provider, model_name, api_key_encrypted, base_url | LLM 配置 |
| shortcuts | id, title, query_text, answer_snapshot(JSON) | 快捷方式 |

### 4.2 Milvus Collection Schema

```
kb_{kb_id}:                         kb_{kb_id}_graph:
┌─────────────────────────┐        ┌─────────────────────────┐
│ id (VARCHAR 128) PK     │        │ id (VARCHAR 128) PK     │
│ chunk_id (VARCHAR 128)  │        │ chunk_id (VARCHAR 128)  │
│ doc_id (VARCHAR 128)    │        │ dense_vector (1024)     │
│ dense_vector (1024)     │        │ sparse_vector (VARCHAR) │
│ sparse_vector (VARCHAR) │        │ content (VARCHAR 8192)  │
│ content (VARCHAR 8192)  │        └─────────────────────────┘
└─────────────────────────┘
  Index: HNSW (M=16, ef=200, COSINE)
  enable_dynamic_field: true
```

### 4.3 Neo4j 图模型

```
(:Entity {id, name, entity_type, kb_id, aliases, ...properties})
    ↕ [:RELATED_TO {relation, weight}]
(:Entity)

(:Chunk {id}) ←[:MENTIONS {chunk_id, doc_id}]-(:Entity)
```

## 五、检索算法细节

### 5.1 HNSW 索引参数

| 参数 | 值 | 说明 |
|------|------|------|
| M | 16 | 每层最大连接数 |
| efConstruction | 200 | 构建时搜索宽度 |
| ef | min(100, N) | 查询时搜索宽度 |
| space | cosine | 余弦相似度 |

### 5.2 BM25 实现

使用 BGE-M3 的 `lexical_weights`（稀疏词权重字典 `{token_id: weight}`）模拟 BM25 效果。匹配时计算 query 和 doc 的 token 重叠加权得分。

### 5.3 RRF 融合公式

```
RRF_score(d) = Σ 1/(k + rank_i(d))

其中 k=60, i ∈ {dense, sparse}
```

### 5.4 图谱检索

```
1. 用户 query → embedding → 搜索 kb_{id}_graph 集合
2. chunk_id 包含 "graph_node_{entity_id}" → 提取 entity_id
3. Neo4j: MATCH (center:Entity {id})-[r*1]-(neighbor) RETURN center, r, neighbor
4. 构建文本:
   - 核心实体: name (type, props)
   - 关联关系: source → relation → target (neighbor type + props)
```

## 六、异常处理体系

```
RAGProError (base)
├── VectorStoreError
│   ├── CollectionNotFoundError
│   ├── DimensionMismatchError
│   ├── VectorInsertError
│   ├── VectorSearchError
│   └── MilvusNotAvailableError
├── GraphStoreError
│   ├── Neo4jNotConnectedError
│   ├── EntityNotFoundError
│   └── GraphBuildError
├── EmbedderError
│   ├── ModelLoadError
│   └── EmbeddingError
├── ExtractionError
│   ├── LLMExtractionError
│   └── EmptyExtractionError
├── DocumentProcessError
│   ├── ParseError
│   ├── ChunkError
│   └── EmptyDocumentError
└── LLMConfigError
    ├── NoLLMConfiguredError
    └── LLMCallError
```
