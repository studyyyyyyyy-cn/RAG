# RAG Pro 完整技术手册

> 从文档上传到智能回答，逐步拆解每个环节的技术实现与代码逻辑。适合没有任何 RAG 基础的小白阅读。

---

## 目录

1. [整体架构概览](#1-整体架构概览)
2. [文档上传与保存](#2-文档上传与保存)
3. [文档解析](#3-文档解析)
4. [文本分块](#4-文本分块)
5. [文本嵌入](#5-文本嵌入)
6. [向量存储](#6-向量存储)
7. [知识图谱构建](#7-知识图谱构建)
8. [用户提问与意图识别](#8-用户提问与意图识别)
9. [文档向量检索](#9-文档向量检索)
10. [图谱向量检索](#10-图谱向量检索)
11. [重排序](#11-重排序)
12. [LLM 生成回答](#12-llm-生成回答)
13. [多智能体输出](#13-多智能体输出)
14. [MCP 外部集成](#14-mcp-外部集成)
15. [异常处理](#15-异常处理)

---

## 1. 整体架构概览

RAG Pro 是一个**检索增强生成（Retrieval-Augmented Generation）**系统。核心思想很简单：

> 用户提一个问题 → 从知识库里找到最相关的几段文字 → 把这些文字作为"参考资料"一起发给大模型 → 大模型基于资料回答问题。

这么做的好处是：大模型不会瞎编，所有答案都有据可查。

整个系统可以拆成两条主线和一条辅线：

```
【主线一：文档入库】
  上传 → 解析 → 分块 → 嵌入（变成向量）→ 存入向量数据库

【主线二：问答检索】
  提问 → 嵌入（同款模型）→ 向量搜索 → 重排序 → 拼提示词 → 大模型回答

【辅线：知识图谱】
  分块完成 → LLM 抽取实体关系 → 写入 Neo4j → 节点/边也嵌入向量
```

---

## 2. 文档上传与保存

### 用户操作

在前端"知识库管理"页面，选择一个知识库，点击上传按钮，选择 PDF/DOCX/CSV/TXT/MD 文件。

### 后端处理

**代码位置**：`backend/app/api/v1/document.py` 第 210-261 行

```python
@router.post("/kb/{kb_id}/documents")
async def upload_documents(kb_id: str, files: list[UploadFile], db: AsyncSession):
```

**处理步骤**：

1. **验证文件类型**：检查后缀是否在允许列表（pdf/csv/txt/md/docx/doc）中，最大 100MB
   ```python
   ext = get_file_extension(file.filename)  # utils/file_handler.py
   ```

2. **保存到磁盘**：每个知识库有一个独立目录 `backend/uploads/{kb_id}/`，文件名加随机 UUID 防止冲突
   ```python
   file_path, file_size = await save_upload_file(content, file.filename, kb_id)
   ```

3. **创建数据库记录**：在 SQLite 的 `documents` 表中插入一行，状态设为 `parsing`
   ```python
   doc = Document(kb_id=kb_id, filename=file.filename, file_type=ext,
                  file_size=file_size, file_path=file_path,
                  parse_status="parsing", chunk_progress=0)
   ```

4. **立即解析**：在上传接口内直接调用解析器，不等到分块阶段
   ```python
   await _parse_document(doc)  # 内部调用 document_parser.parse()
   doc.parse_status = "parsed"
   ```

**关键技术**：
- 文件存储：Python 标准库 `aiofiles` 异步写入
- 数据库：SQLAlchemy 异步 ORM，SQLite 引擎
- 状态流转：`pending → parsing → parsed → chunking → done / failed`

---

## 3. 文档解析

### 代码位置

`backend/app/core/document_parser.py`

### 支持的格式与解析技术

| 格式 | 解析库 | 方法 |
|------|--------|------|
| PDF | PyMuPDF (fitz) | `page.get_text("text")` 逐页提取纯文本 |
| DOCX | python-docx | 按段落读取，识别 Heading 样式作为章节标题 |
| CSV | Python csv 模块 | `csv.DictReader` 读取，每 20 行合成一页 |
| TXT | 原生 open | 按双换行分段，约 2000 字符合成一页 |
| MD | 原生 open | 按 `#` `##` 标题分割段落 |

### PDF 解析示例

```python
def _parse_pdf(self, file_path: str) -> list[DocumentPage]:
    pages = []
    doc = fitz.open(file_path)
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text")
        if text.strip():
            pages.append(DocumentPage(
                text=text.strip(),
                page_number=page_num,
                metadata={"source": Path(file_path).name},
            ))
    doc.close()
    return pages
```

### 编码处理

TXT/CSV/MD 文件可能用不同编码（UTF-8/GBK/Big5 等）。解析器会先用 `chardet` 自动检测编码，然后依次尝试常见编码列表：

```python
encodings = ["utf-8-sig", "utf-8", "utf-16", "gb18030", "gbk", "big5", "latin-1"]
```

### 输出格式

所有解析器返回统一的结构 `DocumentPage`：

```python
@dataclass
class DocumentPage:
    text: str              # 页面文本内容
    page_number: int       # 页码
    section_title: str     # 章节标题（如有）
    metadata: dict         # 源文件名、编码、表头等信息
```

---

## 4. 文本分块

### 为什么需要分块

Embedding 模型一次只能处理有限长度的文本（BGE-M3 最多 8192 个 token），而且大段文本嵌入后会丢失局部细节。所以要把长文档切成小块，每块约 512 个 token。

### 代码位置

`backend/app/core/chunker.py`

### 9 种分块策略

| 策略 | 类名 | 适用场景 | 核心逻辑 |
|------|------|----------|----------|
| 递归分块 | `RecursiveChunker` | **通用默认** | 按 `\n\n → \n → 。 → ，` 的顺序逐级切割，512 token/块，64 token 重叠 |
| 智能分块 | `IntelligentChunker` | 结构化文档 | 先检测标题/段落结构，再对超过 512 token 的部分递归细分 |
| QA 分块 | `QAChunker` | 问答对文档 | 识别 `Q:/问:/A:/答:` 标记，或 CSV 键值对 |
| 表格分块 | `TableChunker` | CSV 数据 | 每行作为一个 chunk，附上表头 |
| 通用分块 | `GeneralChunker` | 固定大小 | 每块固定字符数（chunk_size × 3 ≈ 1536 字符） |
| 朴素分块 | `NaiveChunker` | 简单切分 | 固定字符宽度切分 + overlap |
| 书籍分块 | `BookChunker` | 长文书籍 | 按"第X章"、"Chapter X" 识别章节 |
| 论文分块 | `PaperChunker` | 学术论文 | 按摘要/引言/方法/实验/结论等关键词分段 |
| 简历分块 | `ResumeChunker` | 简历文档 | 按教育/工作/技能/证书等关键词分段 |
| 父子分块 | `ParentChildChunker` | **高质量场景** | 子块 512 token 用于检索，父块 1536 token 作为上下文 |

### 递归分块核心逻辑

```python
class RecursiveChunker:
    SEPARATORS = ["\n\n", "\n", ". ", "；", "。", " ", ""]
    # 从粗到细逐级尝试切割

    def _estimate_tokens(self, text: str) -> int:
        # 中文约 1.5 字符/token，英文约 4 字符/token
        chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)
```

### 父子分块的使用场景

父子分块是最推荐的高质量策略。原理是：

- 检索时：用 512 token 的小块做向量匹配（更精确）
- 回答时：把匹配到的子块对应的 1536 token 大块作为上下文（更完整）

---

## 5. 文本嵌入

### 什么是嵌入（Embedding）

把一段文本变成一个 1024 维的浮点数数组（向量）。两段意思相近的文字，它们的向量在数学空间里距离也近。

```
"今天天气真好" → [0.023, -0.451, 0.892, ...] (1024个数字)
"今天是个好天气" → [0.019, -0.448, 0.887, ...] (向量很接近)
```

### 代码位置

`backend/app/core/embedder.py`

### 支持的嵌入模型

| 模型 | 维度 | 特点 |
|------|------|------|
| `BAAI/bge-m3` | 1024 | **默认**。中英双语，同时输出 dense + sparse（词权重） |
| `paraphrase-MiniLM-L6-v2` | 384 | 轻量，88MB，英文为主 |
| OpenAI Embeddings | 1536~3072 | `text-embedding-3-large/small` |

### BGE-M3 嵌入实现

```python
class BGEM3Embedder(BaseEmbedder):
    def __init__(self, model_name="BAAI/bge-m3", device="cpu"):
        from FlagEmbedding import BGEM3FlagModel
        # 优先加载本地模型（backend/models/BAAI/bge-m3/）
        # 本地没有则从 HuggingFace 下载
        self.model = BGEM3FlagModel(model_path, use_fp16=False)
        self.batch_size = 32

    def embed_documents(self, texts: list[str]) -> dict:
        output = self.model.encode(texts, batch_size=32,
                                   return_dense=True,    # 1024维稠密向量
                                   return_sparse=True,   # 词权重稀疏向量
                                   return_colbert_vecs=False)
        return {
            "dense": output["dense_vecs"],        # (n, 1024) numpy array
            "sparse": output["lexical_weights"],  # [{token_id: weight}, ...]
        }
```

### 模型加载优先级

1. 先检查 `backend/models/` 本地目录
2. 本地没有则从 HuggingFace Hub 下载（国内用 `hf-mirror.com` 镜像）
3. 使用 `_embedder_cache` 字典缓存已加载的模型，避免重复加载

---

## 6. 向量存储

### 代码位置

`backend/app/core/vector_store.py`

### 双模存储架构

| 模式 | 组件 | 适用场景 |
|------|------|----------|
| **Milvus Lite** | 文件型向量数据库 | 本地开发，数据持久化到 `milvus.db` |
| **InMemory** | Numpy 内存存储 | Milvus 不可用时的降级方案 |

### Milvus 初始化

```python
class VectorStore:
    def _init_client(self):
        try:
            from pymilvus import MilvusClient
            self.client = MilvusClient(uri="backend/data/milvus.db")
            # Milvus Lite 是一个嵌入式数据库，不需要额外服务
        except Exception:
            # 降级到内存存储
            self._use_memory = True
            self.client = InMemoryVectorStore(...)
```

### Collection 设计

每个知识库创建两个 Collection：

| Collection | 名称格式 | 存什么 |
|------|------|------|
| 文档向量 | `kb_{kb_id}` | 文档 chunk 的 1024 维向量 + sparse 向量 |
| 图谱向量 | `kb_{kb_id}_graph` | 图谱节点/边的自然语言描述向量 |

### Schema 结构

```python
schema.add_field("id",          VARCHAR, max_length=128, is_primary=True)
schema.add_field("chunk_id",    VARCHAR, max_length=128)  # 关联 SQLite chunks 表
schema.add_field("doc_id",      VARCHAR, max_length=128)  # 关联 documents 表
schema.add_field("dense_vector", FLOAT_VECTOR, dim=1024)  # 核心检索字段
schema.add_field("sparse_vector", VARCHAR, max_length=65535)  # BGE-M3 词权重 JSON
schema.add_field("content",     VARCHAR, max_length=8192) # chunk 文本前 8000 字

# 索引
index_params.add_index("dense_vector", index_type="HNSW", metric_type="COSINE",
                       params={"M": 16, "efConstruction": 200})
```

### HNSW 索引参数解释

| 参数 | 含义 | 影响 |
|------|------|------|
| M=16 | 每个节点最多连 16 个邻居 | 值越大精度越高，内存越大 |
| efConstruction=200 | 构建时搜索范围 | 值越大索引越准，构建越慢 |
| COSINE | 余弦相似度 | 两个向量夹角越小越相似 |

### 降级到内存存储的逻辑

当 Milvus 文件被锁（Windows 常见问题）或启动失败时，自动切换到 `InMemoryVectorStore`：

```python
# InMemoryVectorStore 核心结构
self.collections = {
    "kb_xxx": {
        "vectors": [[0.023, -0.451, ...], ...],        # 所有 1024 维向量
        "sparse_vectors": [{token_id: weight}, ...],    # 词权重
        "metadata": [{"chunk_id": "abc", "content": "..."}, ...]
    }
}
```

---

## 7. 知识图谱构建

### 7.1 什么是知识图谱

把文档里的**实体**（人名、公司、概念）和**关系**（研发、收购、属于）提取出来，存到图数据库中。查询时不只是匹配关键词，还能发现"IBM 和量子计算有什么关系"这种逻辑关联。

### 7.2 实体抽取

**代码位置**：`backend/app/core/entity_extractor.py`

**原理**：用 LLM 从 chunk 文本中抽实体和关系：

```python
EXTRACTION_SYSTEM = """你是一个知识图谱实体关系抽取专家...
实体类型：PERSON/ORGANIZATION/PRODUCT/CONCEPT/LOCATION/TIME/EVENT/ATTRIBUTE
输出格式：{"entities": [{"name":"实体名","type":"实体类型","aliases":[]}],
           "relations": [{"source":"源","target":"目标","relation":"描述"}]}
"""

async def extract_entities_from_text(text: str, llm_config):
    messages = [{"role": "system", "content": EXTRACTION_SYSTEM},
                {"role": "user", "content": f"请从以下文本中提取：\n{text[:3000]}"}]
    result = await chat_completion(messages, llm_config, stream=False)
    # 解析 LLM 返回的 JSON
```

**实体 ID 生成**：用 `MD5(类型:名称)` 的前 16 位，保证同一个实体在多次抽取中 ID 一致。

### 7.3 写入 Neo4j

**代码位置**：`backend/app/core/graph_store.py`

```python
class GraphStore:
    def create_entities(self, kb_id, entities):
        for e in entities:
            session.run("""
                MERGE (n:Entity {id: $id})
                SET n.name = $name, n.entity_type = $entity_type, n.kb_id = $kb_id
            """, id=e.id, name=e.name, entity_type=e.entity_type, kb_id=kb_id)
    # MERGE = 如果已存在就更新，不存在就创建
```

### 7.4 图谱向量化

**代码位置**：`backend/app/core/graph_to_vector.py`

把图谱节点和边转成自然语言文本，再嵌入到向量库：

```python
def node_to_text(entity: dict) -> str:
    # {name: "IBM", entity_type: "ORGANIZATION", properties: {总部: "美国"}}
    # → "IBM是一个组织，总部为美国。"

def edge_to_text(source: str, target: str, relation: str) -> str:
    # ("IBM", "量子计算", "研发")
    # → "IBM研发量子计算。"
```

这样用户提问时，向量检索也能匹配到图谱里的实体和关系。

### 7.5 邻居遍历

```python
def get_neighbors(self, entity_id: str, hops: int = 1):
    # Cypher 查询：找中心实体及其 1 跳范围内的所有邻居和关系
    MATCH (center:Entity {id: $entity_id})
    OPTIONAL MATCH path = (center)-[r:RELATED_TO*1..$hops]-(neighbor:Entity)
    RETURN center, collect(DISTINCT r), collect(DISTINCT neighbor)
```

---

## 8. 用户提问与意图识别

### 代码位置

`backend/app/api/v1/chat.py` + `backend/app/agents/base_agent.py`

### 8.1 SSE 流式对话

用户在前端输入问题 → 前端通过 **Server-Sent Events (SSE)** 接收流式回答，不用等全部生成完就能看到逐字输出。

```python
@router.post("/chat")
async def chat(req: ChatRequest, db: AsyncSession):
    # 创建/获取对话会话
    conversation = Conversation(kb_id=kb.id, title=req.query[:100])
    # 保存用户消息
    user_msg = Message(conversation_id=conversation.id, role="user",
                       content={"text": req.query})
    # 返回 SSE 流
    return StreamingResponse(_sse_stream(...), media_type="text/event-stream")
```

### 8.2 意图检测

用 LLM 判断用户想问什么类型的问题，然后路由到对应的智能体：

```python
INTENT_DETECTION_PROMPT = """分析用户问题，判断最佳回答形式。仅返回以下类型：
- text: 普通文字 - chart: 图表 - report: 报表
- webpage: 网页 - data_table: 数据表格 - knowledge_graph: 知识图谱
用户问题: {query}"""

async def detect_intent(query, llm_config) -> str:
    result = await chat_completion(messages, llm_config, stream=False)
    intent = result.strip().lower()
    if intent in ("text","chart","report","webpage","data_table","knowledge_graph"):
        return intent
    return "text"
```

---

## 9. 文档向量检索

### 代码位置

`backend/app/core/vector_store.py` 第 479-584 行

### 检索流程详解

```python
def hybrid_search(self, kb_id, dense_query, sparse_query=None, top_k=20):
    # dense_query: BGE-M3 输出的 1024 维向量
    # sparse_query: BGE-M3 输出的词权重字典
```

**第一步：加载数据**

```python
all_data = self.client.query(
    collection_name=f"kb_{kb_id}",
    output_fields=["chunk_id","content","dense_vector","sparse_vector"],
    limit=100000
)
```

> 注意：因为 Milvus Lite 的 `search()` 方法有 bug（`function_score` 错误），所以改为先 `query()` 全量拉取，再用 numpy/HNSW 本地计算。

**第二步：HNSW 快速近邻搜索**

```python
# 构建 HNSW 索引（首次搜索时自动构建，后续复用缓存）
def _get_or_build_hnsw(cache_key, all_data):
    import hnswlib
    vectors = np.array([d["dense_vector"] for d in all_data])  # (N, 1024)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)  # 归一化
    index = hnswlib.Index(space='cosine', dim=1024)
    index.init_index(max_elements=len(vectors), ef_construction=200, M=16)
    index.add_items(vectors, np.arange(len(vectors)))
    index.set_ef(100)
    return index

# 搜索
labels, distances = hnsw.knn_query(query_vec, k=60)  # 返回最近的 60 个
```

**第三步：BM25 关键词匹配**

```python
for i, d in enumerate(all_data):
    doc_sparse = json.loads(d["sparse_vector"])       # 文档的词权重
    score = 0.0
    for token_id, qw in query_sparse.items():         # 查询的词权重
        score += qw * doc_sparse.get(str(token_id), 0)  # 重叠加权
    if score > 0:
        sparse_ranked.append((i, score))
```

**第四步：RRF 融合**

```python
rrf_k = 60
rrf_scores = {}
for rank, (idx, _) in enumerate(dense_ranked, 1):
    rrf_scores[idx] = 1.0 / (rrf_k + rank)          # Dense 贡献
for rank, (idx, _) in enumerate(sorted(sparse_ranked, ...), 1):
    rrf_scores[idx] += 1.0 / (rrf_k + rank)          # Sparse 贡献

fused = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:20]
```

**为什么用 RRF 而不是加权求和**

两路分数的量纲完全不同（HNSW 返回的是余弦距离 0~2，BM25 可能是 0~100），没法直接相加。RRF 只看排名不看绝对分数，天然适合异源融合。

---

## 10. 图谱向量检索

### 代码位置

`backend/app/core/retriever.py` 第 173-250 行 + `vector_store.py` `search_graph()`

### 独立于文档检索的图谱搜索

```python
async def _retrieve_graph_context(query, kb_id, query_dense_vector):
    # 1. 搜索图谱向量集合 kb_{id}_graph
    graph_results = vector_store.search_graph(kb_id, query_dense_vector, top_k=5)

    # 2. 从 chunk_id 提取最佳匹配实体
    for gr in graph_results:
        if 'graph_node_' in gr.chunk_id:
            entity_id = gr.chunk_id.replace('graph_node_', '')
            break

    # 3. Neo4j 取邻居
    entity = graph_store.get_entity(entity_id)
    subgraph = graph_store.get_neighbors(entity_id, hops=1)

    # 4. 构建上下文文本
    # "核心实体: IBM（组织，总部:美国，业务:云服务）
    #  关联关系：
    #    IBM 研发 量子计算（概念）[前沿技术]
    #    IBM 总部位于 Armonk（地点）"
```

### 双路检索的 Prompt 结构

```
【匹配统计】
- 文档chunk: 5条
- 图谱节点: 3个
- 图谱关系: 7条

【参考资料】                                   ← 文档向量检索结果
[资料1] IBM年报.pdf - 第12页
IBM operates across five business segments...

【知识图谱上下文】                              ← 图谱检索结果
核心实体: IBM（组织，总部:美国，业务:云服务）
关联关系：
  IBM 研发 量子计算（概念）[前沿技术]
  IBM 收购 Red Hat（组织）[时间:2018年]

---
用户问题: IBM的主要业务是什么？                 ← 原始提问
```

---

## 11. 重排序

### 为什么需要重排序

向量检索是近似的，top-20 里可能有一些不太相关的。重排序器（Cross-Encoder）会把 query 和每个候选 chunk 拼在一起逐对打分，比向量相似度精确得多。

### 代码位置

`backend/app/core/reranker.py`

### Cross-Encoder 原理

```
向量检索（Bi-Encoder）: Query → [vec]; Chunk → [vec]; cos(vec_q, vec_c)
                        ↑ 快但粗糙（一次编码，全量比对）

重排序（Cross-Encoder）: [Query + Chunk] → BERT → Score
                         ↑ 慢但精确（每对要单独过一遍模型）
```

### 实现

```python
class Reranker:
    def __init__(self, model_name="BAAI/bge-reranker-v2-m3"):
        from FlagEmbedding import FlagReranker
        self.model = FlagReranker(model_path, use_fp16=(device != "cpu"))

    def rerank(self, query, passages, top_n=5) -> list[tuple[int, float]]:
        pairs = [[query, passage] for passage in passages]
        scores = self.model.compute_score(pairs, normalize=True)  # 每对打分
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        return indexed_scores[:top_n]  # 取 top-5
```

### 降级方案

```python
def _ensure_model(self):
    try:
        self.model = FlagReranker(model_path)
        return True
    except Exception:
        # 模型不可用时：返回原始顺序 + 递减分数
        return [(i, 1.0 - i * 0.1) for i in range(min(top_n, len(passages)))]
```

---

## 12. LLM 生成回答

### 代码位置

`backend/app/core/generator.py` + `backend/app/utils/prompt_templates.py`

### 系统提示词

```python
SYSTEM_PROMPT_RAG = """你是一个严谨的知识库问答助手。请严格遵守以下规则：
1. **仅基于【参考资料】中的内容回答问题**，不得编造
2. 每个关键论述必须标注来源，格式：[来源: 文档名-页码]
3. 如果参考资料不足以完整回答问题，明确说明原因
4. 回答使用结构化格式（标题、列表、表格等）
5. 在回答开头必须先输出匹配统计"""
```

### 生成流程

```python
async def generate_answer(query, kb_id, db, llm_config_id, stream=True):
    # 1. 检索
    retrieval = await retrieve(query, kb_id, db)

    # 2. 构建提示词
    messages = build_rag_messages(
        query=query,
        context_chunks=retrieval.results,     # 文档 chunk
        graph_context=retrieval.graph_context, # 图谱上下文
        confidence=retrieval.confidence,
    )

    # 3. 调用 LLM
    if stream:
        return _stream_answer(messages, llm_config, citations, retrieval)
    else:
        return await chat_completion(messages, llm_config, stream=False)
```

### LLM 调用层

**代码位置**：`backend/app/core/llm_manager.py`

使用 **LiteLLM** 作为统一网关，支持 100+ LLM 提供商：

```python
PROVIDER_PREFIX = {
    "openai": "",           # 直接使用 OpenAI SDK
    "deepseek": "openai/",  # DeepSeek 兼容 OpenAI 格式
    "anthropic": "anthropic/",
    "ollama": "ollama/",
    "zhipu": "openai/",     # 智谱 API 兼容 OpenAI 格式
}

async def chat_completion(messages, config, stream=True):
    model = f"{prefix}{config.model_name}"
    response = await litellm.acompletion(
        model=model,
        messages=messages,
        temperature=0.1,       # 低温度保证准确性
        max_tokens=4096,
        stream=stream,
        api_key=decrypt_api_key(config.api_key_encrypted),
    )
```

### API Key 加密

```python
# config.py
def encrypt_api_key(raw: str) -> str:
    fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest()))
    return f"enc:{fernet.encrypt(raw.encode()).decode()}"

def decrypt_api_key(encrypted: str) -> str:
    # 支持三种格式: enc:xxx（加密）/ plain:xxx（明文）/ xxx（兼容旧数据）
```

---

## 13. 多智能体输出

### 代码位置

`backend/app/agents/` + `backend/app/core/agent_router.py`

### 智能体注册

```python
AGENTS = {
    "report": report_agent,
    "chart": chart_agent,
    "data_table": data_agent,
    "webpage": webpage_agent,
    "knowledge_graph": graph_agent,
}
```

### 各智能体实现

**图表 Agent** (`chart_agent.py`)：Prompt 模板 → LLM 生成 ECharts JSON → 前端渲染

```python
CHART_PROMPT = """基于参考资料，为用户问题生成一个 ECharts 图表配置。
要求：bar/line/pie/scatter/radar，包含 title/tooltip/legend/series。
仅返回 JSON 对象。"""
```

**报表 Agent** (`report_agent.py`)：Prompt 模板 → LLM 生成语义化 HTML

```python
REPORT_PROMPT = """生成结构化 HTML 报表。使用 h2/h3、table（斑马纹）、ul/ol。
内联 CSS 浅色主题，表格文字用深色。"""
```

**网页 Agent** (`webpage_agent.py`)：生成完整 HTML → 发布为静态文件 → 返回 URL

```python
WEBPAGE_PROMPT = """生成现代卡片式布局网页。HTML+内联CSS+少量JS。
响应式设计，支持折叠面板、标签切换。"""
# 发布
page_url = f"/published-pages/{uuid4().hex}.html"
```

**数据 Agent** (`data_agent.py`)：LLM 输出 JSON `{summary, data_table, chart_spec, insights}`

**图谱 Agent** (`graph_agent.py`)：从 Neo4j 拉取全图 → 生成 ECharts `graph` 类型配置（nodes + links + categories）

### 前端渲染分发

`ChatMessage.vue` 根据 `message.type` 决定用什么组件渲染：

```
text           → markdown-it 渲染 Markdown
chart          → ChartRenderer (ECharts)
report         → ReportViewer (v-html)
webpage        → WebPreview + 链接
data_table     → el-table + ChartRenderer
knowledge_graph → ChartRenderer (ECharts graph 类型)
```

---

## 14. MCP 外部集成

### 什么是 MCP

Model Context Protocol — 允许 Claude Desktop 等外部 AI 客户端直接调用本系统的检索能力。

### 代码位置

`backend/app/mcp/server.py` + `backend/app/mcp/tools.py`

### 协议实现

```
Claude Desktop                     RAG Pro
     │                                │
     ├─ GET /mcp/sse ────────────────→│  建立 SSE 连接
     │← endpoint: /mcp/message ──────│
     │                                │
     ├─ POST /mcp/message ───────────→│  发送 JSON-RPC
     │  {"method":"tools/list"}       │
     │← {"tools": [...]} ────────────│
     │                                │
     ├─ POST /mcp/message ───────────→│  调用工具
     │  {"method":"tools/call",       │
     │   "params":{"name":"rag_chat"}}│
     │← {"content": [...]} ──────────│  返回结果
```

### 提供的工具

| 工具 | 功能 |
|------|------|
| `list_knowledge_bases` | 列出所有知识库 |
| `rag_chat` | RAG 问答 + 智能体路由 |

---

## 15. 异常处理

### 代码位置

`backend/app/core/exceptions.py`

### 异常继承树

```
RAGProError                          # 所有异常基类
├── VectorStoreError                 # 向量库问题
│   ├── DimensionMismatchError       # "Embedder 输出 1024 维，Collection 为 384 维"
│   ├── VectorInsertError            # "向量写入失败: ..."
│   ├── VectorSearchError            # "向量检索失败: function_score"
│   └── MilvusNotAvailableError      # "Milvus 不可用，已降级为内存存储"
├── GraphStoreError                  # 图数据库问题
│   ├── Neo4jNotConnectedError       # "Neo4j 未连接"
│   └── EntityNotFoundError          # "图谱实体不存在"
├── EmbedderError                    # 模型问题
│   └── ModelLoadError               # "模型加载失败: ..."
├── ExtractionError                  # 实体抽取问题
│   ├── LLMExtractionError           # "LLM 实体抽取调用失败"
│   └── EmptyExtractionError         # "文本中未抽取到实体"
├── DocumentProcessError             # 文档处理问题
│   ├── ParseError                   # "文档解析失败"
│   ├── ChunkError                   # "文档分块失败"
│   └── EmptyDocumentError           # "文档无内容可提取（扫描版 PDF？）"
└── LLMConfigError                   # LLM 配置问题
    ├── NoLLMConfiguredError          # "未配置 LLM 模型"
    └── LLMCallError                  # "LLM 调用失败"
```
