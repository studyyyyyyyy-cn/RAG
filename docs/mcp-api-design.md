# MCP和API接口设计方案

## 用户需求

1. 提供MCP接口，让Claude Desktop等AI助手可以调用本系统的RAG能力
2. 提供标准REST API接口
3. 支持问答（RAG检索+LLM生成）功能
4. 保留现有REST API
5. 知识库选择：用户指定模式

---

## MCP工具定义

### 1. list_knowledge_bases

**功能**：列出所有可用的知识库

**参数**：
```python
{
    # 无需参数
}
```

**返回**：
```python
{
    "knowledge_bases": [
        {"id": "kb_001", "name": "产品文档", "description": "产品使用文档"},
        {"id": "kb_002", "name": "技术支持", "description": "常见问题解答"}
    ]
}
```

**使用场景**：用户告诉AI要查询哪个知识库，AI先调用此接口确认知识库ID

---

### 2. rag_chat

**功能**：RAG问答（检索+LLM生成完整答案）

**参数**：
```python
{
    "query": "用户问题",           # 必填
    "kb_id": "知识库ID",          # 必填，用户指定
    "history": [],                # 可选，对话历史
    "top_k": 5                   # 可选，检索片段数，默认5
}
```

**返回**：
```python
{
    "answer": "根据文档内容，答案是...",
    "references": [
        {"source": "文档1.pdf", "page": 1, "content": "相关片段..."},
        {"source": "文档2.docx", "page": 3, "content": "相关片段..."}
    ],
    "confidence": 0.95
}
```

**使用场景**：用户需要AI基于知识库回答问题

---

### 3. rag_search

**功能**：知识检索（仅返回相关文档片段，不生成答案）

**参数**：
```python
{
    "query": "搜索关键词",         # 必填
    "kb_id": "知识库ID",          # 必填，用户指定
    "top_k": 5                   # 可选，返回结果数，默认5
}
```

**返回**：
```python
{
    "results": [
        {
            "content": "相关文档片段内容...",
            "score": 0.95,
            "source": "产品手册.pdf",
            "page_number": 1
        },
        {
            "content": "另一段相关内容...",
            "score": 0.88,
            "source": "FAQ.docx",
            "page_number": 5
        }
    ],
    "total": 2
}
```

**使用场景**：用户只想获取相关参考资料，AI自行判断如何使用

---

## REST API接口

### 1. 问答接口

**端点**：`POST /api/v1/chat`

**功能**：RAG问答

**请求**：
```json
{
    "query": "用户问题",
    "kb_id": "知识库ID",
    "stream": true
}
```

**响应（流式）**：
```
data: {"type": "message", "content": "根据"}
data: {"type": "message", "content": "文档"}
data: {"type": "message", "content": "内容，"}
...
data: {"type": "reference", "source": "文档1.pdf", "page": 1}
data: {"type": "done"}
```

---

### 2. 检索接口

**端点**：`POST /api/v1/retrieve`

**功能**：纯知识检索

**请求**：
```json
{
    "query": "搜索关键词",
    "kb_id": "知识库ID",
    "top_k": 5
}
```

**响应**：
```json
{
    "results": [
        {
            "content": "相关文档片段...",
            "score": 0.95,
            "source": "文档1.pdf",
            "page_number": 1
        }
    ]
}
```

---

### 3. 知识库管理

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/knowledge-bases` | GET | 列出知识库 |
| `/api/v1/knowledge-bases` | POST | 创建知识库 |
| `/api/v1/knowledge-bases/{id}` | DELETE | 删除知识库 |

---

## 用户交互示例

### 场景1：Claude Desktop 问答

**用户**：请帮我查一下产品A的使用说明

**Claude Desktop 调用流程**：

```
1. 用户告知要查询"产品文档"知识库
2. Claude 调用 list_knowledge_bases 确认知识库ID
3. Claude 调用 rag_chat:
   {
     "query": "产品A的使用说明",
     "kb_id": "kb_001"
   }
4. 返回答案和引用
```

**对话示例**：
```
用户: 请帮我查一下产品A的使用说明（知识库：产品文档）

Claude: 我来帮你在"产品文档"知识库中查找。

[调用 rag_chat]
- kb_id: kb_001 (产品文档)
- query: 产品A的使用说明

回答: 根据产品文档，产品A的使用步骤如下：
1. 开机...
2. 配置...

参考资料：
- 产品手册.pdf 第5页
- 快速入门.docx 第1页
```

---

### 场景2：外部系统调用REST API

```bash
# 1. 创建知识库
curl -X POST http://localhost:8000/api/v1/knowledge-bases \
  -H "Content-Type: application/json" \
  -d '{"name": "产品文档", "embedding_model": "BAAI/bge-m3"}'

# 2. 上传文档
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@manual.pdf" \
  -F "kb_id=kb_001"

# 3. RAG问答
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "产品A怎么使用", "kb_id": "kb_001", "stream": true}'

# 4. 纯检索
curl -X POST http://localhost:8000/api/v1/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "使用说明", "kb_id": "kb_001", "top_k": 3}'
```

---

## 技术实现

### 目录结构

```
backend/app/
├── main.py                 # FastAPI入口（修改）
├── config.py               # 配置（添加MCP配置）
├── mcp/
│   ├── __init__.py         # [NEW]
│   ├── server.py           # [NEW] MCP服务器
│   ├── tools.py            # [NEW] MCP工具定义
│   └── resources.py        # [NEW] MCP资源
└── api/v1/
    ├── retrieval.py        # [NEW] 检索接口
```

### 待办事项

- [ ] 创建MCP工具定义（tools.py）
- [ ] 创建MCP服务器（server.py）
- [ ] 集成MCP到FastAPI主应用
- [ ] 创建纯检索REST API接口

---

## MCP Server配置（Claude Desktop）

在 `claude_desktop_config.json` 中配置：

```json
{
  "mcpServers": {
    "ragapp": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "env": {
        "RAGAPP_HOST": "localhost",
        "RAGAPP_PORT": "8000"
      }
    }
  }
}
```

连接成功后，Claude Desktop 会自动发现3个工具：
- `list_knowledge_bases` - 列出知识库
- `rag_chat` - RAG问答
- `rag_search` - 知识检索
