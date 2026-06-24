# RAG应用系统架构设计说明书

## 文档信息

| 项目名称 | RAG知识库问答系统 |
|---------|------------------|
| 版本号 | V1.0 |
| 编写日期 | 2025年2月 |
| 状态 | 正式发布 |

---

## 目录

1. [系统概述](#1-系统概述)
2. [系统架构](#2-系统架构)
3. [核心模块设计](#3-核心模块设计)
4. [问答回复逻辑详解](#4-问答回复逻辑详解)
5. [智能体模块](#5-智能体模块)
6. [检索系统](#6-检索系统)
7. [LLM集成](#7-llm集成)
8. [数据模型](#8-数据模型)
9. [前端架构](#9-前端架构)
10. [部署架构](#10-部署架构)

---

## 1. 系统概述

### 1.1 项目背景

本项目是一个基于RAG（检索增强生成）技术的企业级知识库问答系统，支持多格式文档上传、智能检索、多种输出格式的问答回复，以及快捷方式管理等功能。

### 1.2 核心特性

- **多格式文档支持**：PDF、Word、Excel、Markdown、TXT等
- **混合检索**：密集向量检索 + 稀疏向量检索
- **智能重排序**：Cross-Encoder模型精排
- **多智能体输出**：文本、图表、报表、网页等多种输出格式
- **多LLM支持**：OpenAI、Anthropic、DeepSeek、Ollama等
- **流式响应**：SSE实时流式输出

### 1.3 技术栈

| 层级 | 技术选型 |
|------|---------|
| 前端 | Vue 3 + Element Plus + ECharts |
| 后端 | FastAPI + SQLAlchemy + Uvicorn |
| 数据库 | SQLite（开发）/ PostgreSQL（生产） |
| 向量库 | Milvus Lite / Milvus |
| Embedding | BGE-M3（中英文双语） |
| Reranker | BGE-Reranker-v2-m3 |
| LLM网关 | LiteLLM |

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户界面层                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   问答界面   │  │  知识库管理  │  │  文档管理   │  │  数据看板   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API网关层                                       │
│                         FastAPI + CORS + JWT                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  /api/v1/chat      /api/v1/agent      /api/v1/kb      /api/v1/docs  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              核心业务层                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  Generator  │  │  Retriever  │  │   Agents    │  │ LLM Manager │        │
│  │  (RAG编排)   │  │  (检索器)   │  │  (智能体)   │  │ (LLM管理)   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
┌──────────────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│      检索引擎层       │  │     存储层        │  │    外部服务层        │
│  ┌────────────────┐  │  │ ┌──────────────┐ │  │ ┌──────────────────┐ │
│  │    Embedder    │  │  │ │   SQLite     │ │  │ │   OpenAI API     │ │
│  │   (BGE-M3)     │  │  │ └──────────────┘ │  │ │   Anthropic API  │ │
│  ├────────────────┤  │  │ ┌──────────────┐ │  │ │   DeepSeek API   │ │
│  │   Reranker     │  │  │ │   Milvus     │ │  │ │   Ollama         │ │
│  │(BGE-Reranker)  │  │  │ │   (向量库)   │ │  │ │   其他LLM...     │ │
│  ├────────────────┤  │  │ └──────────────┘ │  │ └──────────────────┘ │
│  │  Vector Store  │  │  │ ┌──────────────┐ │  │                      │
│  │   (Milvus)     │  │  │ │   文件存储   │ │  │                      │
│  └────────────────┘  │  │ └──────────────┘ │  │                      │
└──────────────────────┘  └──────────────────┘  └──────────────────────┘
```

### 2.2 后端目录结构

```
backend/
├── app/
│   ├── main.py                    # FastAPI应用入口
│   ├── config.py                  # 配置管理
│   │
│   ├── api/v1/                    # API路由层
│   │   ├── chat.py                # 聊天问答API (SSE流式)
│   │   ├── agent.py               # 智能体API
│   │   ├── document.py            # 文档管理API
│   │   ├── knowledge.py           # 知识库API
│   │   ├── llm_provider.py        # LLM配置API
│   │   └── shortcut.py            # 快捷方式API
│   │
│   ├── core/                      # 核心模块
│   │   ├── generator.py           # RAG流水线编排
│   │   ├── retriever.py           # 混合检索+重排
│   │   ├── reranker.py            # 重排序模型
│   │   ├── embedder.py            # 向量化模型
│   │   ├── vector_store.py        # 向量数据库
│   │   ├── chunker.py             # 文档分块器
│   │   ├── document_parser.py     # 文档解析器
│   │   ├── llm_manager.py         # LLM统一管理
│   │   └── confidence.py          # 置信度计算
│   │
│   ├── agents/                    # 智能体模块
│   │   ├── base_agent.py          # 基类+意图识别
│   │   ├── chart_agent.py         # 图表智能体
│   │   ├── report_agent.py        # 报表智能体
│   │   ├── data_agent.py          # 数据分析智能体
│   │   └── webpage_agent.py       # 网页智能体
│   │
│   ├── models/                    # 数据模型
│   │   ├── database.py            # 数据库连接
│   │   ├── knowledge_base.py      # 知识库模型
│   │   ├── document.py            # 文档模型
│   │   ├── chunk.py               # 分块模型
│   │   ├── conversation.py        # 会话模型
│   │   └── llm_config.py          # LLM配置模型
│   │
│   └── utils/                     # 工具模块
│       ├── prompt_templates.py    # 提示词模板
│       └── file_handler.py        # 文件处理
│
├── data/                          # 数据目录
├── models/                        # 本地模型目录
└── uploads/                       # 上传文件目录
```

---

## 3. 核心模块设计

### 3.1 模块职责划分

| 模块 | 职责 | 核心文件 |
|------|------|---------|
| API层 | 接收请求、参数验证、响应格式化 | `api/v1/*.py` |
| Generator | RAG流水线编排、协调各组件 | `core/generator.py` |
| Retriever | 文档检索、上下文获取 | `core/retriever.py` |
| Embedder | 文本向量化 | `core/embedder.py` |
| Reranker | 检索结果重排序 | `core/reranker.py` |
| VectorStore | 向量存储与检索 | `core/vector_store.py` |
| Agents | 多格式输出生成 | `agents/*.py` |
| LLMManager | LLM统一调用管理 | `core/llm_manager.py` |

### 3.2 模块间依赖关系

```
┌─────────────┐
│   chat.py   │
│  (API入口)  │
└──────┬──────┘
       │
       ▼
┌─────────────┐      ┌─────────────┐
│  Generator  │─────▶│  Retriever  │
│  (编排器)   │      │  (检索器)   │
└──────┬──────┘      └──────┬──────┘
       │                    │
       │            ┌───────┼───────┐
       │            ▼       ▼       ▼
       │      ┌─────────┬─────────┬─────────┐
       │      │Embedder │Reranker │VectorSt.│
       │      └─────────┴─────────┴─────────┘
       │
       ▼
┌─────────────┐
│LLM Manager  │
│ (LLM调用)   │
└─────────────┘
```

---

## 4. 问答回复逻辑详解

### 4.1 整体流程概览

问答回复是系统的核心功能，采用RAG（检索增强生成）架构，通过"检索-重排-生成"三阶段流程，结合用户历史对话上下文，生成准确的回复。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           问答回复完整流程                                   │
└─────────────────────────────────────────────────────────────────────────────┘

用户提问 ──────────────────────────────────────────────────────────────────────▶
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 阶段1: 请求预处理                                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1.1 验证知识库存在                                                           │
│ 1.2 获取或创建会话（Conversation）                                           │
│ 1.3 加载历史消息（最近6条，用于上下文）                                        │
│ 1.4 保存用户消息到数据库                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 阶段2: 知识检索（Retriever）                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2.1 查询向量化（BGE-M3: dense + sparse）                                     │
│ 2.2 混合向量检索（Milvus: top_k=20）                                         │
│ 2.3 重排序（BGE-Reranker: top_n=5）                                          │
│ 2.4 获取父块上下文（Parent-Child策略）                                        │
│ 2.5 计算置信度分数                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 阶段3: 提示词构建                                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3.1 构建系统提示词（System Prompt）                                          │
│ 3.2 注入检索到的上下文                                                        │
│ 3.3 添加历史对话记录                                                          │
│ 3.4 组装完整消息列表                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 阶段4: LLM生成                                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ 4.1 获取LLM配置（模型、API Key、参数）                                        │
│ 4.2 通过LiteLLM调用LLM                                                       │
│ 4.3 流式/非流式响应处理                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 阶段5: 响应返回                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ 5.1 SSE流式返回（event: metadata/text_chunk/done/complete）                  │
│ 5.2 保存助手消息到数据库                                                      │
│ 5.3 返回消息ID、会话ID                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 阶段1: 请求预处理

**入口文件**: `backend/app/api/v1/chat.py`  
**核心函数**: `chat()` (第27-119行)

#### 1.1 请求参数

```python
class ChatRequest(BaseModel):
    kb_id: str                    # 知识库ID
    query: str                    # 用户问题
    conversation_id: str | None   # 会话ID（可选）
    llm_config_id: str | None     # LLM配置ID（可选）
```

#### 1.2 预处理步骤

```python
async def chat(request: ChatRequest, db: AsyncSession):
    # 1. 验证知识库
    kb = await db.get(KnowledgeBase, request.kb_id)
    if not kb:
        raise HTTPException(404, "Knowledge base not found")
    
    # 2. 获取或创建会话
    if request.conversation_id:
        conv = await db.get(Conversation, request.conversation_id)
    else:
        conv = Conversation(kb_id=request.kb_id, title=request.query[:50])
        db.add(conv)
        await db.flush()
    
    # 3. 获取历史消息（最近6条）
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at.desc())
        .limit(6)
    )
    history = list(reversed(history_result.scalars().all()))
    
    # 4. 保存用户消息
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content={"text": request.query}
    )
    db.add(user_msg)
    await db.commit()
```

### 4.3 阶段2: 知识检索

**核心文件**: `backend/app/core/retriever.py`  
**核心函数**: `retrieve()` (第41-124行)

#### 2.1 检索流程图

```
查询文本 (query)
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤2.1: 查询向量化                                              │
│ ─────────────────────────────────────────────────────────────── │
│ 模型: BGE-M3 (BAAI/bge-m3)                                      │
│ 输出:                                                           │
│   - dense向量: 1024维浮点数组（语义密集表示）                     │
│   - sparse向量: 词ID到权重的映射（词汇精确匹配）                  │
│                                                                 │
│ 代码位置: embedder.embed_query(query)                           │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤2.2: 混合向量检索                                            │
│ ─────────────────────────────────────────────────────────────── │
│ 引擎: Milvus                                                    │
│ 策略:                                                           │
│   - 密集向量检索: 余弦相似度搜索                                 │
│   - 稀疏向量检索: BM25风格词频匹配                               │
│   - 融合: 加权合并两种检索结果                                   │
│ 参数:                                                           │
│   - top_k: 20 (候选文档数量)                                     │
│   - collection: {kb_id} (按知识库隔离)                           │
│                                                                 │
│ 代码位置: vector_store.hybrid_search(dense, sparse, top_k=20)   │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤2.3: 重排序                                                  │
│ ─────────────────────────────────────────────────────────────── │
│ 模型: BGE-Reranker-v2-m3 (Cross-Encoder)                        │
│ 原理:                                                           │
│   - 输入: (query, passage) 对                                    │
│   - 输出: 相关性得分 (0-1)                                       │
│   - 优势: 比向量相似度更精确                                     │
│ 参数:                                                           │
│   - top_n: 5 (最终保留数量)                                      │
│                                                                 │
│ 代码位置: reranker.rerank(query, passages, top_n=5)             │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤2.4: 获取父块上下文                                          │
│ ─────────────────────────────────────────────────────────────── │
│ 策略: Parent-Child Chunking                                     │
│   - 子块 (child): 512 tokens, 用于检索                          │
│   - 父块 (parent): 1536 tokens, 用于上下文                       │
│                                                                 │
│ 处理:                                                           │
│   - 检索到的是子块                                               │
│   - 通过parent_chunk_id查找对应的父块                            │
│   - 使用父块内容作为上下文，提供更完整的信息                       │
│                                                                 │
│ 代码位置: 根据 chunk.parent_chunk_id 查询数据库                   │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤2.5: 置信度计算                                              │
│ ─────────────────────────────────────────────────────────────── │
│ 公式: confidence = 0.6 * max_score + 0.4 * avg_score            │
│                                                                 │
│ 分级:                                                           │
│   - high: confidence >= 0.7                                     │
│   - medium: 0.5 <= confidence < 0.7                             │
│   - low: 0.3 <= confidence < 0.5                                │
│   - very_low: confidence < 0.3                                  │
│                                                                 │
│ 代码位置: confidence.compute_confidence(rerank_scores)          │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
检索结果: contexts (上下文列表), confidence (置信度)
```

#### 2.2 检索核心代码

```python
# retriever.py
async def retrieve(
    query: str,
    kb_id: str,
    db: AsyncSession,
    top_k: int = 20,
    top_n: int = 5,
) -> tuple[list[dict], float]:
    """检索相关文档并重排序"""
    
    # 1. 查询向量化
    embeddings = embedder.embed_query(query)
    dense_vec = embeddings["dense"]
    sparse_vec = embeddings.get("sparse")
    
    # 2. 混合检索
    candidates = vector_store.hybrid_search(
        collection_name=kb_id,
        dense_vector=dense_vec,
        sparse_vector=sparse_vec,
        top_k=top_k
    )
    
    # 3. 重排序
    passages = [c["content"] for c in candidates]
    reranked = reranker.rerank(query, passages, top_n=top_n)
    
    # 4. 获取父块上下文
    contexts = []
    for item in reranked:
        chunk_id = candidates[item["index"]]["chunk_id"]
        chunk = await db.get(Chunk, chunk_id)
        
        # 获取父块
        if chunk.parent_chunk_id:
            parent = await db.get(Chunk, chunk.parent_chunk_id)
            content = parent.content
        else:
            content = chunk.content
        
        contexts.append({
            "content": content,
            "source": chunk.document.filename,
            "score": item["score"]
        })
    
    # 5. 计算置信度
    scores = [item["score"] for item in reranked]
    confidence = compute_confidence(scores)
    
    return contexts, confidence
```

### 4.4 阶段3: 提示词构建

**核心文件**: `backend/app/utils/prompt_templates.py`  
**核心函数**: `build_rag_messages()` (第35行)

#### 3.1 提示词模板结构

```python
RAG_SYSTEM_PROMPT = """你是一个专业的知识库问答助手。
请基于以下参考资料回答用户问题。

要求：
1. 优先使用参考资料中的信息
2. 如果参考资料不足以回答问题，请诚实说明
3. 回答要简洁准确，引用来源
4. 使用中文回答

参考资料：
{context}
"""

def build_rag_messages(
    query: str,
    contexts: list[dict],
    history: list[Message],
) -> list[dict]:
    """构建RAG提示词消息列表"""
    
    # 1. 构建上下文字符串
    context_text = "\n\n---\n\n".join([
        f"[来源: {c['source']}]\n{c['content']}"
        for c in contexts
    ])
    
    # 2. 构建消息列表
    messages = [
        {"role": "system", "content": RAG_SYSTEM_PROMPT.format(context=context_text)}
    ]
    
    # 3. 添加历史对话
    for msg in history:
        messages.append({
            "role": msg.role,
            "content": msg.content.get("text", "")
        })
    
    # 4. 添加当前问题
    messages.append({"role": "user", "content": query})
    
    return messages
```

#### 3.2 消息列表示例

```python
messages = [
    {
        "role": "system",
        "content": "你是一个专业的知识库问答助手...\n参考资料：\n[来源: 产品手册.pdf]\n产品A支持..."
    },
    {
        "role": "user",
        "content": "产品A有哪些功能？"
    },
    {
        "role": "assistant",
        "content": "根据产品手册，产品A支持..."
    },
    {
        "role": "user",
        "content": "那价格是多少？"  # 当前问题
    }
]
```

### 4.5 阶段4: LLM生成

**核心文件**: `backend/app/core/llm_manager.py`  
**核心函数**: `chat_completion()` (第47-81行)

#### 4.1 LLM调用流程

```
┌─────────────────────────────────────────────────────────────────┐
│ 步骤4.1: 获取LLM配置                                             │
│ ─────────────────────────────────────────────────────────────── │
│ 来源: llm_configs 表                                            │
│ 字段:                                                           │
│   - provider: openai/anthropic/deepseek/ollama...              │
│   - model_name: gpt-4o/claude-sonnet-4/deepseek-chat...        │
│   - api_key_encrypted: 加密的API密钥                            │
│   - base_url: 自定义API地址                                     │
│   - params: {temperature, max_tokens, ...}                     │
│   - is_default: 是否为默认配置                                   │
│                                                                 │
│ 逻辑: 如果未指定config_id，使用is_default=True的配置             │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤4.2: 构建LiteLLM模型字符串                                   │
│ ─────────────────────────────────────────────────────────────── │
│ 映射规则:                                                       │
│   - openai → "gpt-4o"                                           │
│   - anthropic → "anthropic/claude-sonnet-4"                     │
│   - deepseek → "deepseek/deepseek-chat"                         │
│   - ollama → "ollama/llama3"                                    │
│   - zhipu/qwen/vllm → OpenAI兼容格式                            │
│                                                                 │
│ 代码: _build_litellm_model(config)                              │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤4.3: 调用LLM                                                 │
│ ─────────────────────────────────────────────────────────────── │
│ 方式1: 流式响应 (stream=True)                                   │
│   - 返回 AsyncGenerator[str, None]                              │
│   - 用于实时显示生成内容                                         │
│                                                                 │
│ 方式2: 非流式响应 (stream=False)                                │
│   - 返回完整文本 str                                            │
│   - 用于智能体处理等场景                                         │
│                                                                 │
│ 代码: litellm.acompletion(model, messages, stream=..., ...)     │
└─────────────────────────────────────────────────────────────────┘
```

#### 4.2 核心代码

```python
# llm_manager.py
async def chat_completion(
    messages: list[dict],
    config: LLMConfig,
    stream: bool = True,
    **kwargs
) -> AsyncGenerator[str, None] | str:
    """统一的LLM调用入口"""
    
    # 构建模型字符串
    model = _build_litellm_model(config)
    
    # 合并参数
    params = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "api_key": decrypt(config.api_key_encrypted),
        **config.params,
        **kwargs
    }
    
    # 自定义base_url
    if config.base_url:
        params["api_base"] = config.base_url
    
    # 调用LLM
    response = await litellm.acompletion(**params)
    
    if stream:
        return _stream_response(response)
    else:
        return response.choices[0].message.content
```

### 4.6 阶段5: 响应返回

#### 5.1 SSE事件格式

```
event: metadata
data: {"confidence": 0.85, "citations": [{"source": "产品手册.pdf"}]}

event: text_chunk
data: {"text": "根据产品手册，"}

event: text_chunk
data: {"text": "产品A支持以下功能："}

event: text_chunk
data: {"text": "1. 功能一\n2. 功能二"}

event: done
data: {}

event: complete
data: {"message_id": "xxx", "conversation_id": "yyy"}
```

#### 5.2 响应处理代码

```python
# chat.py
async def chat(request: ChatRequest, db: AsyncSession):
    # ... 前面的预处理步骤 ...
    
    # 生成回答
    contexts, confidence = await retriever.retrieve(
        query=request.query,
        kb_id=request.kb_id,
        db=db
    )
    
    messages = build_rag_messages(request.query, contexts, history)
    llm_config = await get_llm_config(db, request.llm_config_id)
    
    async def generate():
        # 发送元数据
        yield f"event: metadata\ndata: {json.dumps({'confidence': confidence, 'citations': contexts})}\n\n"
        
        # 流式生成
        full_text = ""
        async for chunk in chat_completion(messages, llm_config, stream=True):
            full_text += chunk
            yield f"event: text_chunk\ndata: {json.dumps({'text': chunk})}\n\n"
        
        # 发送完成信号
        yield "event: done\ndata: {}\n\n"
        
        # 保存消息
        assistant_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content={"text": full_text},
            citations=[{"source": c["source"]} for c in contexts],
            confidence=confidence
        )
        db.add(assistant_msg)
        await db.commit()
        
        # 发送完成信息
        yield f"event: complete\ndata: {json.dumps({'message_id': str(assistant_msg.id), 'conversation_id': str(conv.id)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

### 4.7 完整时序图

```
┌──────┐     ┌──────┐     ┌──────┐     ┌──────┐     ┌──────┐     ┌──────┐     ┌──────┐
│ 前端  │     │ API  │     │Gener.│     │Retri.│     │Vector│     │Rerank│     │ LLM  │
└──┬───┘     └──┬───┘     └──┬───┘     └──┬───┘     └──┬───┘     └──┬───┘     └──┬───┘
   │            │            │            │            │            │            │
   │ POST /chat │            │            │            │            │            │
   │───────────▶│            │            │            │            │            │
   │            │ 验证/获取会话│            │            │            │            │
   │            │───────────▶│            │            │            │            │
   │            │            │ retrieve() │            │            │            │
   │            │            │───────────▶│            │            │            │
   │            │            │            │ embed_query│            │            │
   │            │            │            │───────────▶│            │            │
   │            │            │            │◀───────────│            │            │
   │            │            │            │ hybrid_srch│            │            │
   │            │            │            │───────────▶│            │            │
   │            │            │            │◀───────────│            │            │
   │            │            │            │ rerank()   │            │            │
   │            │            │            │───────────────────────▶│            │
   │            │            │            │◀───────────────────────│            │
   │            │            │◀───────────│            │            │            │
   │            │            │ build_msgs │            │            │            │
   │            │            │─────────────────────────────────────────────────▶│
   │            │            │            │            │            │            │
   │ SSE stream │            │            │            │            │            │
   │◀───────────│◀───────────│◀───────────────────────────────────────────────│
   │            │            │            │            │            │            │
   │ event:done │            │            │            │            │            │
   │◀───────────│◀───────────│            │            │            │            │
   │            │            │            │            │            │            │
```

---

## 5. 智能体模块

### 5.1 智能体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                       BaseAgent (抽象基类)                       │
│  - agent_type: str                                               │
│  - execute(query, context, llm_config) -> dict                  │
│  - detect_intent(query) -> str (意图识别)                        │
└─────────────────────────────────────────────────────────────────┘
         △                △                △                △
         │                │                │                │
    ┌────┴────┐      ┌────┴────┐      ┌────┴────┐      ┌────┴────┐
    │ Chart   │      │ Report  │      │  Data   │      │ Webpage │
    │ Agent   │      │  Agent  │      │  Agent  │      │  Agent  │
    └─────────┘      └─────────┘      └─────────┘      └─────────┘
```

### 5.2 智能体类型

| 智能体 | 输出类型 | 输出格式 | 应用场景 |
|--------|---------|---------|---------|
| ChartAgent | chart | ECharts JSON配置 | 数据可视化图表 |
| ReportAgent | report | HTML报表 | 结构化数据报告 |
| DataAgent | composite | JSON（表格+图表+洞察） | 综合数据分析 |
| WebpageAgent | webpage | HTML+CSS+JS | 交互式网页展示 |

### 5.3 意图识别

```python
# base_agent.py
INTENT_KEYWORDS = {
    "chart": ["图表", "折线图", "柱状图", "饼图", "可视化", "趋势"],
    "report": ["报表", "报告", "汇总", "统计表", "数据表"],
    "webpage": ["网页", "页面", "展示页", "HTML"],
    "data_table": ["数据表", "表格", "分析数据"],
}

def detect_intent(query: str) -> str:
    """根据关键词识别用户意图"""
    query_lower = query.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(kw in query_lower for kw in keywords):
            return intent
    return "text"  # 默认纯文本回复
```

### 5.4 智能体执行流程

```
POST /api/v1/agent/execute
         │
         ▼
┌─────────────────────────────────┐
│ 1. 验证知识库                    │
│ 2. 获取LLM配置                   │
│ 3. 意图检测（如未指定类型）       │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 4. retriever.retrieve()         │
│    检索相关上下文                │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 5. agent.execute()              │
│    执行对应智能体                │
│    - ChartAgent: 生成ECharts    │
│    - ReportAgent: 生成HTML      │
│    - DataAgent: 生成复合输出    │
│    - WebpageAgent: 生成网页     │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 6. 保存消息到数据库              │
│ 7. 返回结果                      │
└─────────────────────────────────┘
```

### 5.5 ReportAgent详解

```python
# report_agent.py
class ReportAgent(BaseAgent):
    agent_type = "report"

    async def execute(self, query: str, context: list[dict], llm_config: LLMConfig) -> dict:
        # 构建提示词
        prompt = REPORT_PROMPT.format(context=context_text, query=query)
        
        # 调用LLM生成HTML
        html_content = await chat_completion([{"role": "user", "content": prompt}], llm_config, stream=False)
        
        # 返回结构化结果
        return {
            "type": "report",
            "content": {
                "text": "根据知识库数据为您生成了以下报表：",
                "html_content": html_content,
                "citations": [...]
            }
        }
```

---

## 6. 检索系统

### 6.1 检索流程详解

```
┌─────────────────────────────────────────────────────────────────┐
│                      检索系统架构                                │
└─────────────────────────────────────────────────────────────────┘

用户查询
    │
    ▼
┌─────────────┐     ┌─────────────┐
│   Embedder  │────▶│ Dense Vec   │ 1024维语义向量
│   (BGE-M3)  │     │ Sparse Vec  │ 词权重映射
└─────────────┘     └─────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Vector Store (Milvus)                         │
│  ┌─────────────────┐       ┌─────────────────┐                  │
│  │  Dense Index    │       │ Sparse Index    │                  │
│  │  (IVF_FLAT)     │       │ (SparseFloat)   │                  │
│  │  余弦相似度      │       │ BM25风格        │                  │
│  └─────────────────┘       └─────────────────┘                  │
│           │                        │                             │
│           └──────────┬─────────────┘                             │
│                      ▼                                           │
│              混合检索结果 (top_k=20)                              │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Reranker (BGE-Reranker-v2-m3)                  │
│                                                                  │
│  输入: (query, passage) 对                                        │
│  模型: Cross-Encoder                                             │
│  输出: 相关性得分 (0-1)                                           │
│                                                                  │
│  精排后结果 (top_n=5)                                             │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Parent-Child Context                           │
│                                                                  │
│  子块 (512 tokens) ──▶ 检索命中 ──▶ 获取父块 (1536 tokens)         │
│                                                                  │
│  父块提供更完整的上下文信息                                        │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 向量化模型

| 模型 | 维度 | 特点 |
|------|------|------|
| BGE-M3 | dense: 1024, sparse: 动态 | 中英文双语，支持密集+稀疏向量 |
| OpenAI | 1536 | 需要API调用 |
| SentenceTransformer | 可变 | 轻量级本地模型 |

### 6.3 重排序模型

```python
# reranker.py
class Reranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self.model_name = model_name
        self._model = None
    
    @property
    def model(self):
        """懒加载模型"""
        if self._model is None:
            from FlagEmbedding import FlagReranker
            self._model = FlagReranker(self.model_name, use_fp16=True)
        return self._model
    
    def rerank(self, query: str, passages: list[str], top_n: int = 5) -> list[dict]:
        """重排序"""
        pairs = [[query, p] for p in passages]
        scores = self.model.compute_score(pairs, normalize=True)
        
        results = [
            {"index": i, "score": scores[i]}
            for i in range(len(passages))
        ]
        return sorted(results, key=lambda x: x["score"], reverse=True)[:top_n]
```

---

## 7. LLM集成

### 7.1 支持的LLM提供商

| 提供商 | 前缀 | 模型示例 |
|--------|------|---------|
| OpenAI | (无) | gpt-4o, gpt-4-turbo |
| Anthropic | anthropic/ | claude-sonnet-4, claude-3-opus |
| DeepSeek | deepseek/ | deepseek-chat, deepseek-reasoner |
| Ollama | ollama/ | llama3, qwen2 |
| 智谱AI | (OpenAI兼容) | glm-4 |
| 通义千问 | (OpenAI兼容) | qwen-turbo |
| VLLM | (OpenAI兼容) | 自定义模型 |

### 7.2 LLM配置模型

```python
# models/llm_config.py
class LLMConfig(Base):
    __tablename__ = "llm_configs"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    provider: Mapped[str]           # openai/anthropic/deepseek...
    model_name: Mapped[str]         # gpt-4o/claude-sonnet-4...
    display_name: Mapped[str]       # 显示名称
    api_key_encrypted: Mapped[str]  # 加密的API密钥
    base_url: Mapped[str | None]    # 自定义API地址
    is_default: Mapped[bool]        # 是否默认
    params: Mapped[dict]            # temperature, max_tokens等
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

---

## 8. 数据模型

### 8.1 核心实体关系

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│KnowledgeBase│────▶│  Document   │────▶│   Chunk     │
│             │     │             │     │             │
│ id          │     │ id          │     │ id          │
│ name        │     │ filename    │     │ content     │
│ description │     │ file_type   │     │ chunk_index │
│ embedding_  │     │ file_size   │     │ page_number │
│   model     │     │ total_chunks│     │ token_count │
│ chunk_size  │     │ parse_status│     │ parent_chunk│
└─────────────┘     └─────────────┘     └─────────────┘
       │
       │
       ▼
┌─────────────┐     ┌─────────────┐
│Conversation │────▶│   Message   │
│             │     │             │
│ id          │     │ id          │
│ kb_id       │     │ conversation│
│ title       │     │ role        │
│ created_at  │     │ content     │
└─────────────┘     │ citations   │
                    │ confidence  │
                    │ type        │
                    └─────────────┘
```

### 8.2 数据库表结构

| 表名 | 说明 | 主要字段 |
|------|------|---------|
| knowledge_bases | 知识库 | id, name, embedding_model, chunk_size |
| documents | 文档 | id, kb_id, filename, parse_status |
| chunks | 分块 | id, doc_id, content, parent_chunk_id |
| conversations | 会话 | id, kb_id, title |
| messages | 消息 | id, conversation_id, role, content, type |
| llm_configs | LLM配置 | id, provider, model_name, is_default |
| shortcuts | 快捷方式 | id, title, answer_snapshot |

---

## 9. 前端架构

### 9.1 技术栈

- **框架**: Vue 3 + Composition API
- **UI组件**: Element Plus
- **图表**: ECharts + vue-echarts
- **状态管理**: Pinia
- **路由**: Vue Router
- **HTTP**: Axios
- **Markdown**: markdown-it + highlight.js

### 9.2 目录结构

```
frontend/src/
├── views/              # 页面组件
│   ├── Chat.vue        # 问答界面
│   ├── KnowledgeBase.vue # 知识库管理
│   ├── DocumentManager.vue # 文档管理
│   ├── Shortcuts.vue   # 快捷方式
│   ├── Dashboard.vue   # 数据看板
│   └── Settings.vue    # 系统设置
│
├── components/         # 公共组件
│   ├── ChatMessage.vue # 消息气泡
│   ├── ChartRenderer.vue # 图表渲染
│   ├── ReportViewer.vue # 报表查看
│   └── FileUploader.vue # 文件上传
│
├── stores/            # 状态管理
│   ├── chat.js        # 聊天状态
│   └── kb.js          # 知识库状态
│
├── api/               # API封装
│   └── index.js       # 接口定义
│
└── router/            # 路由配置
    └── index.js
```

### 9.3 核心组件交互

```
┌─────────────────────────────────────────────────────────────────┐
│                         Chat.vue                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   Sidebar   │  │ MessageList │  │   Input     │              │
│  │  (历史会话)  │  │             │  │   Area      │              │
│  └─────────────┘  └──────┬──────┘  └─────────────┘              │
│                          │                                      │
│                          ▼                                      │
│                   ┌─────────────┐                               │
│                   │ ChatMessage │                               │
│                   │  (消息组件)  │                               │
│                   └──────┬──────┘                               │
│                          │                                      │
│         ┌────────────────┼────────────────┐                     │
│         ▼                ▼                ▼                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ TextContent │  │ChartRenderer│  │ReportViewer │              │
│  │ (Markdown)  │  │  (ECharts)  │  │   (HTML)    │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 10. 部署架构

### 10.1 开发环境

```
┌─────────────────────────────────────────────────────────────────┐
│                        开发环境部署                               │
│                                                                  │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐        │
│  │   前端      │     │   后端      │     │   数据      │        │
│  │ Vite Dev    │     │ Uvicorn     │     │ SQLite      │        │
│  │ :5173       │     │ :8000       │     │ ragapp.db   │        │
│  └─────────────┘     └─────────────┘     └─────────────┘        │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    本地模型                               │    │
│  │  BGE-M3 (Embedding) + BGE-Reranker-v2-m3 (Reranker)     │    │
│  │  CPU/GPU                                                 │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 10.2 生产环境

```
┌─────────────────────────────────────────────────────────────────┐
│                        生产环境部署                               │
│                                                                  │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐        │
│  │   Nginx     │────▶│   后端      │────▶│ PostgreSQL  │        │
│  │   反向代理   │     │ Uvicorn     │     │   数据库    │        │
│  │   :80/443   │     │ 多实例      │     │             │        │
│  └─────────────┘     └─────────────┘     └─────────────┘        │
│         │                   │                                    │
│         │                   ▼                                    │
│         │            ┌─────────────┐                            │
│         │            │   Milvus    │                            │
│         │            │  向量数据库  │                            │
│         │            └─────────────┘                            │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────┐                                                │
│  │   前端      │                                                │
│  │ 静态文件    │                                                │
│  │ (Vue构建)   │                                                │
│  └─────────────┘                                                │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    外部服务                               │    │
│  │  OpenAI API / Anthropic API / DeepSeek API / Ollama     │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 10.3 Docker部署

```yaml
# docker-compose.yml
version: '3.8'
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://...
      - MILVUS_HOST=milvus
    depends_on:
      - postgres
      - milvus

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend

  postgres:
    image: postgres:15
    volumes:
      - pgdata:/var/lib/postgresql/data

  milvus:
    image: milvusdb/milvus:latest
    ports:
      - "19530:19530"
```

---

## 附录

### A. 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| DEFAULT_EMBEDDING_MODEL | BAAI/bge-m3 | 默认向量化模型 |
| DEFAULT_RERANKER_MODEL | BAAI/bge-reranker-v2-m3 | 默认重排序模型 |
| RETRIEVAL_TOP_K | 20 | 混合检索候选数 |
| RERANK_TOP_N | 5 | 重排序后保留数 |
| CONFIDENCE_THRESHOLD | 0.3 | 置信度阈值 |
| DEFAULT_CHUNK_SIZE | 512 | 子块大小(tokens) |
| PARENT_CHUNK_SIZE | 1536 | 父块大小(tokens) |
| EMBEDDING_DEVICE | cpu | 向量化设备 |

### B. API端点

| 端点 | 方法 | 说明 |
|------|------|------|
| /api/v1/chat | POST | 问答聊天(SSE) |
| /api/v1/agent/execute | POST | 智能体执行 |
| /api/v1/kb | GET/POST | 知识库列表/创建 |
| /api/v1/kb/{id} | GET/PUT/DELETE | 知识库操作 |
| /api/v1/kb/{id}/documents | GET/POST | 文档列表/上传 |
| /api/v1/kb/{id}/documents/{doc_id}/chunks | GET | 分块列表 |
| /api/v1/conversations | GET | 会话列表 |
| /api/v1/shortcuts | GET/POST | 快捷方式列表/创建 |

### C. 错误码

| 错误码 | 说明 |
|--------|------|
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用（模型加载失败等） |

---

*文档版本: V1.0 | 最后更新: 2025年2月*
