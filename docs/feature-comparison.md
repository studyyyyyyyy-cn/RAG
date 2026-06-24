# 系统功能对比与改进建议

## 与 RAGFlow 的功能对比

### 当前系统已有功能 ✅

#### 1. 文档上传与处理
- ✅ 多文件批量上传
- ✅ 支持格式：PDF、DOCX、DOC、CSV、TXT、MD
- ✅ 上传进度显示
- ✅ 处理状态跟踪（解析 → 分块 → 向量化）
- ✅ 父子分块策略
- ✅ 混合向量检索（密集+稀疏）
- ✅ 文档管理（查看、删除）
- ✅ 分块详情查看

#### 2. 测试与调试功能
- ✅ API 测试页面（支持流式/非流式）
- ✅ 置信度显示（百分比+等级）
- ✅ 引用来源显示（相关度分数+页码）
- ✅ 原始 JSON 响应查看
- ✅ 智能体路由测试

#### 3. 检索过程可视化
- ✅ 置信度徽章（高/中/低/极低）
- ✅ 相关度分数显示
- ✅ 参考来源引用
- ✅ 页码和章节信息

---

### 缺失的核心功能 ❌

#### 1. 文档处理功能

| 功能 | RAGFlow | 本系统 | 优先级 |
|------|---------|--------|--------|
| OCR 识别（扫描件） | ✅ | ❌ | 🔴 高 |
| 表格结构识别 | ✅ | ❌ | 🔴 高 |
| 图片提取与理解 | ✅ | ❌ | 🟡 中 |
| 多语言识别 | ✅ | ⚠️ 部分 | 🟡 中 |
| 文档预处理（去噪） | ✅ | ❌ | 🟢 低 |
| 版面分析 | ✅ | ❌ | 🟡 中 |

**影响**：
- 无法处理扫描版 PDF
- 表格数据丢失结构信息
- 图表内容无法理解

---

#### 2. 测试问答模块（重要缺失！）

**RAGFlow 的测试问答功能**：
```
文档上传完成后 → 进入"测试问答"模式
├─ 输入测试问题
├─ 实时显示检索过程：
│   ├─ 查询改写（Query Rewriting）
│   ├─ 向量检索结果（Top-K）
│   ├─ 每个分块的匹配分数
│   ├─ 重排序过程
│   └─ 最终选中的上下文
├─ 显示生成过程：
│   ├─ 使用的 Prompt 模板
│   ├─ 输入的上下文
│   └─ LLM 生成的答案
└─ 性能指标：
    ├─ 检索耗时
    ├─ 生成耗时
    └─ Token 消耗
```

**本系统当前状态**：
- ❌ 没有独立的"测试问答"模块
- ⚠️ API 测试页面只显示最终结果
- ⚠️ 缺少检索过程的详细展示
- ⚠️ 缺少 Prompt 模板查看
- ⚠️ 缺少性能指标统计

**用户痛点**：
1. 文档上传后，不知道分块效果如何
2. 问答效果不好时，无法定位问题（是检索问题还是生成问题？）
3. 无法调试和优化检索参数
4. 无法验证文档是否被正确理解

---

#### 3. 检索过程可视化（部分缺失）

**RAGFlow 提供的详细信息**：
```json
{
  "query": "原始问题",
  "rewritten_query": "改写后的查询",
  "retrieval_results": [
    {
      "chunk_id": "xxx",
      "content": "分块内容",
      "dense_score": 0.85,
      "sparse_score": 0.72,
      "hybrid_score": 0.79,
      "rerank_score": 0.91,
      "final_score": 0.91,
      "document": "文档名.pdf",
      "page": 5,
      "section": "第三章"
    }
  ],
  "selected_chunks": [...],  // 最终选中的分块
  "context_length": 2048,
  "prompt_template": "...",
  "llm_response": "...",
  "metrics": {
    "retrieval_time_ms": 120,
    "rerank_time_ms": 80,
    "generation_time_ms": 1500,
    "total_tokens": 3500
  }
}
```

**本系统当前返回**：
```json
{
  "answer": "答案内容",
  "confidence": 0.85,
  "confidence_label": "high",
  "sources": [
    {
      "content": "引用内容",
      "relevance": 0.91,
      "page_number": 5,
      "section_title": "第三章"
    }
  ]
}
```

**缺失的关键信息**：
- ❌ 查询改写过程
- ❌ 多阶段评分（dense/sparse/hybrid/rerank）
- ❌ 检索到但未选中的分块
- ❌ Prompt 模板
- ❌ 性能指标（耗时、Token 数）
- ❌ 上下文长度统计

---

#### 4. 分块策略配置

| 功能 | RAGFlow | 本系统 |
|------|---------|--------|
| 多种分块策略选择 | ✅ 5种+ | ⚠️ 2种 |
| 可视化分块预览 | ✅ | ❌ |
| 分块效果评估 | ✅ | ❌ |
| 自定义分块规则 | ✅ | ❌ |
| 分块边界调整 | ✅ | ❌ |

---

#### 5. 知识库管理

| 功能 | RAGFlow | 本系统 |
|------|---------|--------|
| 知识库版本管理 | ✅ | ❌ |
| 文档去重 | ✅ | ❌ |
| 增量更新 | ✅ | ❌ |
| 文档标签分类 | ✅ | ❌ |
| 权限管理 | ✅ | ❌ |

---

## 改进建议

### 优先级 1：实现测试问答模块 🔴

这是最重要的缺失功能！

#### 前端实现

**新增页面**：`DocumentTestChat.vue`

```vue
<template>
  <div class="test-chat-container">
    <!-- 左侧：问答区域 -->
    <div class="chat-panel">
      <el-input
        v-model="testQuery"
        placeholder="输入测试问题"
        @keyup.enter="testQuery"
      />
      <div class="answer-display">
        {{ answer }}
      </div>
    </div>

    <!-- 右侧：检索过程详情 -->
    <div class="debug-panel">
      <el-tabs>
        <!-- Tab 1: 检索过程 -->
        <el-tab-pane label="检索过程">
          <el-timeline>
            <el-timeline-item title="查询改写">
              原始: {{ originalQuery }}
              改写: {{ rewrittenQuery }}
            </el-timeline-item>

            <el-timeline-item title="向量检索">
              <div v-for="chunk in retrievalResults" :key="chunk.id">
                <el-card>
                  <div class="chunk-scores">
                    Dense: {{ chunk.dense_score }}
                    Sparse: {{ chunk.sparse_score }}
                    Hybrid: {{ chunk.hybrid_score }}
                  </div>
                  <div class="chunk-content">
                    {{ chunk.content }}
                  </div>
                </el-card>
              </div>
            </el-timeline-item>

            <el-timeline-item title="重排序">
              <div v-for="chunk in rerankedResults" :key="chunk.id">
                Rerank Score: {{ chunk.rerank_score }}
              </div>
            </el-timeline-item>

            <el-timeline-item title="上下文构建">
              选中 {{ selectedChunks.length }} 个分块
              总长度: {{ contextLength }} tokens
            </el-timeline-item>
          </el-timeline>
        </el-tab-pane>

        <!-- Tab 2: Prompt 查看 -->
        <el-tab-pane label="Prompt">
          <el-input
            type="textarea"
            :rows="20"
            v-model="promptTemplate"
            readonly
          />
        </el-tab-pane>

        <!-- Tab 3: 性能指标 -->
        <el-tab-pane label="性能">
          <el-descriptions :column="2">
            <el-descriptions-item label="检索耗时">
              {{ metrics.retrieval_time_ms }} ms
            </el-descriptions-item>
            <el-descriptions-item label="重排序耗时">
              {{ metrics.rerank_time_ms }} ms
            </el-descriptions-item>
            <el-descriptions-item label="生成耗时">
              {{ metrics.generation_time_ms }} ms
            </el-descriptions-item>
            <el-descriptions-item label="总耗时">
              {{ metrics.total_time_ms }} ms
            </el-descriptions-item>
            <el-descriptions-item label="输入 Tokens">
              {{ metrics.input_tokens }}
            </el-descriptions-item>
            <el-descriptions-item label="输出 Tokens">
              {{ metrics.output_tokens }}
            </el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <!-- Tab 4: 原始数据 -->
        <el-tab-pane label="原始 JSON">
          <pre>{{ JSON.stringify(debugData, null, 2) }}</pre>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>
```

#### 后端实现

**新增接口**：`POST /api/v1/kb/{kb_id}/test-chat`

```python
# backend/app/api/v1/document.py

@router.post("/kb/{kb_id}/test-chat")
async def test_chat(
    kb_id: str,
    query: str,
    top_k: int = 5,
    enable_rerank: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """测试问答接口，返回详细的检索和生成过程"""
    import time

    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(404, "Knowledge base not found")

    debug_data = {
        "query": query,
        "rewritten_query": None,
        "retrieval_results": [],
        "reranked_results": [],
        "selected_chunks": [],
        "prompt_template": None,
        "answer": None,
        "metrics": {}
    }

    # 1. 查询改写（可选）
    start_time = time.time()
    rewritten_query = await query_rewriter.rewrite(query)  # 需要实现
    debug_data["rewritten_query"] = rewritten_query

    # 2. 向量检索
    retrieval_start = time.time()
    embedder = get_embedder(kb.embedding_model)
    query_embedding = embedder.embed_query(rewritten_query or query)

    # 调用 Milvus 检索
    search_results = vector_store.search(
        kb_id=str(kb_id),
        dense_vector=query_embedding["dense"],
        sparse_vector=query_embedding.get("sparse"),
        top_k=top_k * 2,  # 检索更多候选
        return_scores=True,  # 返回各阶段分数
    )

    retrieval_time = (time.time() - retrieval_start) * 1000

    # 构建检索结果详情
    for result in search_results:
        chunk = await db.get(Chunk, result["chunk_id"])
        debug_data["retrieval_results"].append({
            "chunk_id": result["chunk_id"],
            "content": chunk.content[:200] + "...",
            "dense_score": result["dense_score"],
            "sparse_score": result.get("sparse_score"),
            "hybrid_score": result["hybrid_score"],
            "document": chunk.document.filename,
            "page": chunk.page_number,
            "section": chunk.section_title,
        })

    # 3. 重排序
    if enable_rerank:
        rerank_start = time.time()
        reranker = get_reranker()
        reranked = reranker.rerank(
            query=rewritten_query or query,
            documents=[r["content"] for r in debug_data["retrieval_results"]],
        )
        rerank_time = (time.time() - rerank_start) * 1000

        # 更新分数
        for i, score in enumerate(reranked["scores"]):
            debug_data["retrieval_results"][i]["rerank_score"] = score

        # 按重排序分数排序
        debug_data["reranked_results"] = sorted(
            debug_data["retrieval_results"],
            key=lambda x: x["rerank_score"],
            reverse=True
        )[:top_k]
    else:
        rerank_time = 0
        debug_data["reranked_results"] = debug_data["retrieval_results"][:top_k]

    # 4. 构建上下文
    selected_chunks = debug_data["reranked_results"]
    context = "\n\n".join([c["content"] for c in selected_chunks])
    context_length = len(context.split())  # 粗略估算

    debug_data["selected_chunks"] = selected_chunks
    debug_data["context_length"] = context_length

    # 5. 构建 Prompt
    prompt_template = """基于以下上下文回答问题：

上下文：
{context}

问题：{question}

请给出准确、详细的回答："""

    prompt = prompt_template.format(
        context=context,
        question=query
    )
    debug_data["prompt_template"] = prompt

    # 6. 调用 LLM 生成
    generation_start = time.time()
    llm = get_llm(kb.llm_model)
    response = await llm.generate(prompt)
    generation_time = (time.time() - generation_start) * 1000

    debug_data["answer"] = response["text"]

    # 7. 统计指标
    debug_data["metrics"] = {
        "retrieval_time_ms": round(retrieval_time, 2),
        "rerank_time_ms": round(rerank_time, 2),
        "generation_time_ms": round(generation_time, 2),
        "total_time_ms": round((time.time() - start_time) * 1000, 2),
        "input_tokens": response.get("input_tokens", 0),
        "output_tokens": response.get("output_tokens", 0),
        "total_tokens": response.get("total_tokens", 0),
    }

    return debug_data
```

#### 入口集成

在文档管理页面添加"测试问答"按钮：

```vue
<!-- DocumentManager.vue -->
<el-button
  type="primary"
  @click="openTestChat(doc.id)"
  :disabled="doc.parse_status !== 'done'"
>
  测试问答
</el-button>
```

---

### 优先级 2：增强检索过程可视化 🟡

#### 修改现有接口

在 `/api/v1/chat` 接口中添加 `debug=true` 参数：

```python
@router.post("/chat")
async def chat(
    request: ChatRequest,
    debug: bool = False,  # 新增调试模式
    db: AsyncSession = Depends(get_db),
):
    if debug:
        # 返回详细的调试信息
        return detailed_response_with_debug_info
    else:
        # 返回正常响应
        return normal_response
```

#### 前端显示优化

在 Chat 页面添加"调试模式"开关：

```vue
<el-switch
  v-model="debugMode"
  active-text="调试模式"
/>

<!-- 调试信息面板 -->
<el-drawer v-model="showDebugPanel" title="检索详情" size="50%">
  <el-descriptions :column="1">
    <el-descriptions-item label="检索耗时">
      {{ debugInfo.retrieval_time_ms }} ms
    </el-descriptions-item>
    <el-descriptions-item label="检索到的分块数">
      {{ debugInfo.retrieval_results.length }}
    </el-descriptions-item>
  </el-descriptions>

  <el-divider>检索结果</el-divider>
  <el-table :data="debugInfo.retrieval_results">
    <el-table-column prop="content" label="内容" width="300" />
    <el-table-column prop="hybrid_score" label="混合分数" width="100" />
    <el-table-column prop="rerank_score" label="重排序分数" width="120" />
    <el-table-column prop="page" label="页码" width="80" />
  </el-table>
</el-drawer>
```

---

### 优先级 3：添加 OCR 和表格识别 🔴

#### OCR 功能

**方案 1：使用 PaddleOCR**

```python
# backend/app/core/ocr.py

from paddleocr import PaddleOCR

class OCRProcessor:
    def __init__(self):
        self.ocr = PaddleOCR(use_angle_cls=True, lang='ch')

    def extract_text_from_image(self, image_path: str) -> str:
        """从图片中提取文字"""
        result = self.ocr.ocr(image_path, cls=True)
        texts = []
        for line in result:
            for word_info in line:
                texts.append(word_info[1][0])
        return "\n".join(texts)

    def extract_text_from_pdf(self, pdf_path: str) -> list[str]:
        """从扫描版 PDF 中提取文字"""
        import fitz
        doc = fitz.open(pdf_path)
        pages_text = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            # 将页面转为图片
            pix = page.get_pixmap()
            img_path = f"/tmp/page_{page_num}.png"
            pix.save(img_path)

            # OCR 识别
            text = self.extract_text_from_image(img_path)
            pages_text.append(text)

        return pages_text
```

**方案 2：使用 Tesseract OCR**

```python
import pytesseract
from PIL import Image

def ocr_image(image_path: str) -> str:
    image = Image.open(image_path)
    text = pytesseract.image_to_string(image, lang='chi_sim+eng')
    return text
```

#### 表格识别

**方案 1：使用 pdfplumber**

```python
# backend/app/core/table_extractor.py

import pdfplumber

class TableExtractor:
    def extract_tables_from_pdf(self, pdf_path: str) -> list[dict]:
        """提取 PDF 中的表格"""
        tables_data = []

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()

                for table_idx, table in enumerate(tables):
                    # 转换为结构化文本
                    table_text = self._table_to_text(table)
                    tables_data.append({
                        "page": page_num + 1,
                        "table_index": table_idx,
                        "content": table_text,
                        "rows": len(table),
                        "cols": len(table[0]) if table else 0,
                    })

        return tables_data

    def _table_to_text(self, table: list[list]) -> str:
        """将表格转换为文本格式"""
        if not table:
            return ""

        # 方式1：Markdown 表格
        lines = []
        for row in table:
            lines.append("| " + " | ".join(str(cell or "") for cell in row) + " |")

        # 添加表头分隔线
        if len(lines) > 1:
            header_sep = "| " + " | ".join(["---"] * len(table[0])) + " |"
            lines.insert(1, header_sep)

        return "\n".join(lines)
```

**方案 2：使用 camelot-py**

```python
import camelot

def extract_tables_camelot(pdf_path: str) -> list:
    tables = camelot.read_pdf(pdf_path, pages='all')
    return [table.df.to_markdown() for table in tables]
```

#### 集成到文档解析器

```python
# backend/app/core/document_parser.py

class DocumentParser:
    def __init__(self):
        self.ocr_processor = OCRProcessor()
        self.table_extractor = TableExtractor()

    def parse(self, file_path: str) -> list[DocumentPage]:
        ext = Path(file_path).suffix.lower()

        if ext == ".pdf":
            # 先尝试普通文本提取
            pages = self._parse_pdf(file_path)

            # 检测是否为扫描件（文本很少）
            if self._is_scanned_pdf(pages):
                # 使用 OCR
                pages = self._parse_pdf_with_ocr(file_path)

            # 提取表格
            tables = self.table_extractor.extract_tables_from_pdf(file_path)
            pages = self._merge_tables_into_pages(pages, tables)

            return pages

        # ... 其他格式处理

    def _is_scanned_pdf(self, pages: list[DocumentPage]) -> bool:
        """判断是否为扫描件"""
        total_text = "".join(p.text for p in pages)
        return len(total_text.strip()) < 100  # 文本太少，可能是扫描件
```

---

### 优先级 4：分块效果预览 🟡

#### 前端实现

在文档详情页添加"分块预览"功能：

```vue
<!-- DocumentChunkPreview.vue -->
<template>
  <div class="chunk-preview">
    <el-card v-for="(chunk, index) in chunks" :key="index">
      <template #header>
        <div class="chunk-header">
          <span>分块 #{{ chunk.chunk_index }}</span>
          <el-tag>{{ chunk.token_count }} tokens</el-tag>
          <el-tag type="info">页码: {{ chunk.page_number }}</el-tag>
        </div>
      </template>

      <div class="chunk-content">
        {{ chunk.content }}
      </div>

      <!-- 显示与前一个分块的重叠部分 -->
      <el-divider v-if="index > 0">
        <el-tag type="warning" size="small">
          重叠部分（{{ calculateOverlap(chunks[index-1], chunk) }} 字符）
        </el-tag>
      </el-divider>

      <!-- 父分块信息 -->
      <el-collapse v-if="chunk.parent_chunk_id">
        <el-collapse-item title="查看父分块">
          <div class="parent-chunk">
            {{ chunk.parent_content }}
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>
```

---

### 优先级 5：性能监控面板 🟢

#### 新增页面：`SystemMonitor.vue`

```vue
<template>
  <div class="monitor-dashboard">
    <el-row :gutter="20">
      <!-- 检索性能 -->
      <el-col :span="12">
        <el-card title="检索性能">
          <v-chart :option="retrievalChartOption" />
          <el-descriptions :column="2">
            <el-descriptions-item label="平均耗时">
              {{ avgRetrievalTime }} ms
            </el-descriptions-item>
            <el-descriptions-item label="P95 耗时">
              {{ p95RetrievalTime }} ms
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <!-- 生成性能 -->
      <el-col :span="12">
        <el-card title="生成性能">
          <v-chart :option="generationChartOption" />
          <el-descriptions :column="2">
            <el-descriptions-item label="平均耗时">
              {{ avgGenerationTime }} ms
            </el-descriptions-item>
            <el-descriptions-item label="平均 Tokens">
              {{ avgTokens }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <!-- 慢查询日志 -->
    <el-card title="慢查询日志（>2s）">
      <el-table :data="slowQueries">
        <el-table-column prop="query" label="查询" />
        <el-table-column prop="total_time" label="总耗时" />
        <el-table-column prop="retrieval_time" label="检索耗时" />
        <el-table-column prop="generation_time" label="生成耗时" />
        <el-table-column prop="timestamp" label="时间" />
      </el-table>
    </el-card>
  </div>
</template>
```

#### 后端实现

```python
# backend/app/api/v1/monitor.py

@router.get("/monitor/metrics")
async def get_metrics(
    time_range: str = "1h",  # 1h, 24h, 7d
    db: AsyncSession = Depends(get_db),
):
    """获取系统性能指标"""
    # 从日志或数据库中统计
    metrics = {
        "retrieval": {
            "avg_time_ms": 120,
            "p95_time_ms": 250,
            "p99_time_ms": 500,
        },
        "generation": {
            "avg_time_ms": 1500,
            "avg_tokens": 350,
        },
        "slow_queries": [
            {
                "query": "复杂问题...",
                "total_time": 3500,
                "retrieval_time": 500,
                "generation_time": 3000,
                "timestamp": "2024-03-18 10:30:00"
            }
        ]
    }
    return metrics
```

---

## 实施路线图

### 第一阶段（1-2周）：核心功能补齐
1. ✅ 实现测试问答模块（前端+后端）
2. ✅ 增强检索过程可视化
3. ✅ 添加性能指标统计

### 第二阶段（2-3周）：文档处理增强
1. ✅ 集成 OCR 功能（PaddleOCR）
2. ✅ 实现表格识别（pdfplumber）
3. ✅ 添加分块效果预览

### 第三阶段（1-2周）：体验优化
1. ✅ 实现性能监控面板
2. ✅ 添加文档去重
3. ✅ 优化分块策略配置

---

## 总结

### 最关键的缺失功能

1. **测试问答模块**（🔴 最高优先级）
   - 这是 RAGFlow 的核心优势
   - 对调试和优化至关重要
   - 用户强烈需要

2. **检索过程详细展示**（🔴 高优先级）
   - 多阶段评分可视化
   - Prompt 模板查看
   - 性能指标统计

3. **OCR 和表格识别**（🟡 中优先级）
   - 扩展文档支持范围
   - 提升数据提取质量

### 快速实施建议

**第一步**：先实现测试问答模块的基础版本
- 前端：简单的问答界面 + 检索结果展示
- 后端：返回检索详情和性能指标
- 预计 3-5 天完成

**第二步**：逐步完善调试信息
- 添加多阶段评分
- 添加 Prompt 查看
- 添加性能图表
- 预计 5-7 天完成

**第三步**：根据用户反馈优化
- 收集用户使用数据
- 优化界面交互
- 添加更多调试选项

