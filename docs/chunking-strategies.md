# 文档分块策略说明

## 概述

本系统采用智能文档分块技术，将上传的文档切分为适合检索和理解的文本片段。合理的分块策略是 RAG 系统性能的关键因素之一。

## 分块方式

### 1. 递归字符分块（Recursive Character Splitting）

**原理**：按照预定义的分隔符层级递归切分文本，保持语义完整性。

**分隔符优先级**：
```
1. 段落分隔符：\n\n（双换行）
2. 行分隔符：\n（单换行）
3. 句子分隔符：. ；。
4. 词语分隔符：空格
5. 字符级切分：""（最后手段）
```

**核心参数**：
- `chunk_size`：目标分块大小（默认 512 tokens）
- `chunk_overlap`：相邻分块重叠大小（默认 64 tokens）

**工作流程**：
1. 从最高优先级分隔符开始尝试切分
2. 如果切分后的片段仍超过目标大小，使用下一级分隔符递归切分
3. 在相邻分块之间添加重叠内容，保持上下文连贯性

**Token 估算**：
- 中文：约 1.5 字符/token
- 英文：约 4 字符/token

**优点**：
- 保持文本语义完整性
- 避免在句子中间截断
- 支持中英文混合文本

**适用场景**：
- 通用文档处理
- 长文本分块
- 需要保持段落结构的文档

---

### 2. 父子分块（Parent-Child Chunking）

**原理**：采用两级分块策略，小块用于精确检索，大块提供完整上下文。

**分块层级**：

#### 子分块（Child Chunks）
- **大小**：512 tokens（可配置）
- **重叠**：64 tokens
- **用途**：向量化并存储到向量数据库，用于语义检索
- **特点**：粒度细，检索精确度高

#### 父分块（Parent Chunks）
- **大小**：1536 tokens（约 3 倍子分块）
- **重叠**：0 tokens
- **用途**：提供更完整的上下文信息
- **特点**：包含更多背景信息，避免上下文丢失

**工作流程**：
1. 首先将文档切分为大的父分块（1536 tokens）
2. 对每个父分块再切分为多个子分块（512 tokens）
3. 子分块记录其所属的父分块索引
4. 检索时：
   - 使用子分块进行向量检索（精确匹配）
   - 返回时提取对应的父分块内容（完整上下文）

**数据结构**：
```python
子分块 {
    text: "具体内容片段",
    chunk_index: 0,
    parent_chunk_index: 0,  # 指向父分块
    page_number: 1,
    token_count: 512
}

父分块 {
    text: "更大的上下文内容",
    chunk_index: 0,
    page_number: 1,
    token_count: 1536
}
```

**优点**：
- 检索精度高：小块匹配更精确
- 上下文完整：返回大块避免信息丢失
- 平衡性能：检索快速，理解准确

**缺点**：
- 存储开销较大（需存储两级分块）
- 处理时间稍长

**适用场景**：
- 需要高精度检索的场景
- 文档内容上下文依赖性强
- 对答案质量要求高的应用

---

## 系统实现

### 当前配置

本系统默认采用**父子分块策略**，配置如下：

```python
# 知识库创建时的默认配置
chunk_size = 512        # 子分块大小
chunk_overlap = 64      # 子分块重叠
parent_size = 1536      # 父分块大小（自动计算为 3x chunk_size）
```

### 分块流程

```
文档上传
    ↓
文档解析（提取文本、页码、章节）
    ↓
父分块切分（1536 tokens）
    ↓
子分块切分（512 tokens，带重叠）
    ↓
向量化（仅对子分块）
    ↓
存储到数据库
    ├─ PostgreSQL：存储分块元数据和文本
    └─ Milvus：存储子分块向量
```

### 数据库设计

**Chunk 表结构**：
```sql
CREATE TABLE chunks (
    id VARCHAR(36) PRIMARY KEY,
    doc_id VARCHAR(36),              -- 所属文档
    kb_id VARCHAR(36),               -- 所属知识库
    content TEXT,                    -- 分块内容
    chunk_index INTEGER,             -- 分块序号
    parent_chunk_id VARCHAR(36),     -- 父分块ID（NULL表示是父分块）
    page_number INTEGER,             -- 页码
    section_title VARCHAR(300),      -- 章节标题
    token_count INTEGER,             -- Token数量
    milvus_id VARCHAR(100),          -- Milvus向量ID
    created_at TIMESTAMP
);
```

**区分父子分块**：
- 父分块：`parent_chunk_id IS NULL`
- 子分块：`parent_chunk_id IS NOT NULL`

### 检索流程

1. **向量检索**：在 Milvus 中检索相似的子分块
2. **获取父分块**：根据 `parent_chunk_id` 查询对应的父分块
3. **返回上下文**：将父分块内容作为上下文提供给 LLM

---

## 与 RAGFlow 的对比

### RAGFlow 的分块方式

RAGFlow 提供了多种分块策略：

#### 1. 智能分块（Intelligent Chunking）
- 基于文档结构（标题、段落、列表）进行分块
- 保持语义完整性
- 适合结构化文档（PDF、Word）

#### 2. 通用分块（General Chunking）
- 固定大小分块，类似本系统的递归分块
- 支持自定义分块大小和重叠
- 适合纯文本文档

#### 3. 问答分块（Q&A Chunking）
- 针对问答对格式优化
- 每个问答对作为一个独立分块
- 适合 FAQ 文档

#### 4. 表格分块（Table Chunking）
- 专门处理表格数据
- 保持表格结构完整性
- 适合数据密集型文档

### 本系统的优势

| 特性 | 本系统 | RAGFlow |
|------|--------|---------|
| 父子分块 | ✅ 默认启用 | ❌ 不支持 |
| 递归分块 | ✅ 支持 | ✅ 支持 |
| 智能分块 | ⚠️ 部分支持 | ✅ 完整支持 |
| 表格处理 | ❌ 不支持 | ✅ 支持 |
| 配置灵活性 | ⚠️ 中等 | ✅ 高 |
| 实现复杂度 | 🟢 简单 | 🟡 中等 |

### 选择建议

**使用本系统的场景**：
- 通用文档问答
- 需要完整上下文的场景
- 快速部署和使用

**使用 RAGFlow 的场景**：
- 复杂文档结构（多级标题、表格）
- 需要精细化分块控制
- 特定领域文档（法律、医疗）

---

## 最佳实践

### 1. 分块大小选择

**小分块（256-512 tokens）**：
- ✅ 检索精度高
- ✅ 向量相似度计算快
- ❌ 上下文可能不完整
- **适用**：事实性问答、关键词检索

**中等分块（512-1024 tokens）**：
- ✅ 平衡精度和上下文
- ✅ 适合大多数场景
- **适用**：通用问答、文档理解

**大分块（1024-2048 tokens）**：
- ✅ 上下文完整
- ❌ 检索精度可能下降
- ❌ 向量计算开销大
- **适用**：需要长上下文的复杂推理

### 2. 重叠大小选择

**推荐比例**：10-20% 的分块大小

```
chunk_size = 512  →  chunk_overlap = 50-100
chunk_size = 1024 →  chunk_overlap = 100-200
```

**重叠的作用**：
- 避免关键信息在分块边界丢失
- 提供上下文连续性
- 提高检索召回率

**注意事项**：
- 重叠过大：存储浪费，检索冗余
- 重叠过小：可能丢失跨块信息

### 3. 文档类型优化

**技术文档**：
- 分块大小：512-768 tokens
- 保留代码块完整性
- 保留章节标题信息

**法律文档**：
- 分块大小：768-1024 tokens
- 保持条款完整性
- 记录条款编号

**对话记录**：
- 分块大小：256-512 tokens
- 按对话轮次分块
- 保留说话人信息

**学术论文**：
- 分块大小：512-1024 tokens
- 保留章节结构
- 保留引用信息

---

## 性能优化

### 1. 向量化优化

```python
# 批量向量化，而非逐个处理
texts = [chunk.text for chunk in chunks]
embeddings = embedder.embed_documents(texts)  # 批量处理
```

### 2. 存储优化

- 仅对子分块进行向量化（节省存储和计算）
- 父分块仅存储文本（PostgreSQL）
- 使用 Milvus 的稀疏+密集混合检索

### 3. 检索优化

```python
# 检索流程
1. 向量检索子分块（top_k=5）
2. 获取对应的父分块ID
3. 去重父分块（避免重复）
4. 返回父分块内容作为上下文
```

---

## 配置示例

### 创建知识库时配置分块参数

```python
# API 请求示例
POST /api/v1/knowledge-bases
{
    "name": "技术文档库",
    "description": "公司内部技术文档",
    "chunk_size": 512,        # 子分块大小
    "chunk_overlap": 64,      # 重叠大小
    "embedding_model": "bge-m3"
}
```

### 查看分块结果

```python
# 获取文档的分块列表
GET /api/v1/kb/{kb_id}/documents/{doc_id}/chunks

# 响应示例
{
    "total": 45,
    "items": [
        {
            "id": "chunk-uuid-1",
            "chunk_index": 0,
            "content": "第一章 系统架构...",
            "token_count": 487,
            "page_number": 1,
            "parent_chunk_id": "parent-uuid-1"
        }
    ]
}
```

---

## 常见问题

### Q1: 为什么检索结果不准确？

**可能原因**：
- 分块过大，导致向量表示不精确
- 分块过小，丢失关键上下文
- 重叠不足，跨块信息丢失

**解决方案**：
- 调整 `chunk_size` 为 512-768
- 设置 `chunk_overlap` 为 64-128
- 使用父子分块策略

### Q2: 如何处理表格和代码？

**当前限制**：
- 表格会被转换为纯文本
- 代码块保持完整性（通过递归分块）

**改进方向**：
- 实现表格专用分块器
- 代码块语义分块

### Q3: 分块后如何保留文档结构？

**当前实现**：
- 记录页码（`page_number`）
- 记录章节标题（`section_title`）
- 保留元数据（`metadata`）

**使用方式**：
```python
# 检索时可以过滤特定页码或章节
chunks = retriever.search(
    query="系统架构",
    filters={"page_number": 5}
)
```

---

## 参考资料

- [LangChain Text Splitters](https://python.langchain.com/docs/modules/data_connection/document_transformers/)
- [RAGFlow Documentation](https://github.com/infiniflow/ragflow)
- [Chunking Strategies for RAG](https://www.pinecone.io/learn/chunking-strategies/)

---

## 更新日志

- **2024-02-28**：初始版本，实现递归分块和父子分块
- **2024-03-18**：完善文档说明，添加最佳实践

