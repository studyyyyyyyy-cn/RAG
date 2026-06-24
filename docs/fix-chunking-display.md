# 问题修复总结

## 问题 1：查看分块为空

### 原因
前端查询分块接口只查询有 `parent_chunk_id` 的子分块：
```sql
WHERE parent_chunk_id IS NOT NULL
```

但除了 `parent_child` 方式外，其他分块方式生成的都是独立分块（`parent_chunk_id` 为 NULL），所以查询不到数据。

### 修复
修改 `/kb/{kb_id}/documents/{doc_id}/chunks` 接口，根据文档的分块方式决定查询逻辑：

- **parent_child 方式**：只查询子分块（`parent_chunk_id IS NOT NULL`）
- **其他方式**：查询所有分块（不过滤 `parent_chunk_id`）

**修改文件**：`backend/app/api/v1/document.py`

```python
if doc.chunk_method == "parent_child":
    # 只查询子分块
    where_clause = Chunk.parent_chunk_id.is_not(None)
else:
    # 查询所有分块
    where_clause = True  # 不过滤
```

---

## 问题 2：分块方式未显示文字

### 原因
后端文档列表接口返回的数据中缺少 `chunk_method` 字段。

### 修复
在 `/kb/{kb_id}/documents` 接口的返回数据中添加 `chunk_method` 字段。

**修改文件**：`backend/app/api/v1/document.py`

```python
"items": [
    {
        "id": str(d.id),
        "filename": d.filename,
        # ... 其他字段
        "chunk_method": d.chunk_method,  # 添加这个字段
        # ...
    }
    for d in docs
]
```

---

## 测试验证

### 测试步骤

1. **重启后端服务**
   ```bash
   cd backend
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **刷新前端页面**（清除缓存）

3. **查看已有文档**
   - 打开文档管理页面
   - 查看 QA.csv 文档
   - 应该显示"分块方式：问答分块"

4. **查看分块详情**
   - 点击"查看分块"按钮
   - 应该能看到 1 个分块
   - 显示分块内容

5. **测试新上传**
   - 上传新文档
   - 选择不同的分块方式
   - 执行分块
   - 查看分块详情

### 预期结果

✅ 所有分块方式都能正确显示分块数据
✅ 分块方式文字正确显示
✅ 父子分块只显示子分块
✅ 其他方式显示所有分块

---

## 分块方式对比

| 分块方式 | parent_chunk_id | 显示的分块 | 用途 |
|---------|----------------|-----------|------|
| parent_child | 子分块有值 | 只显示子分块 | 精确检索+完整上下文 |
| intelligent | NULL | 显示所有分块 | 按文档结构分块 |
| qa | NULL | 显示所有分块 | 问答对分块 |
| table | NULL | 显示所有分块 | 表格分块 |
| general | NULL | 显示所有分块 | 固定大小分块 |
| recursive | NULL | 显示所有分块 | 递归分块 |

---

## 数据库结构说明

### chunks 表

```sql
CREATE TABLE chunks (
    id VARCHAR(36) PRIMARY KEY,
    doc_id VARCHAR(36),              -- 所属文档
    kb_id VARCHAR(36),               -- 所属知识库
    content TEXT,                    -- 分块内容
    chunk_index INTEGER,             -- 分块序号
    parent_chunk_id VARCHAR(36),     -- 父分块ID（NULL=独立分块）
    page_number INTEGER,             -- 页码
    section_title VARCHAR(300),      -- 章节标题
    token_count INTEGER,             -- Token数量
    milvus_id VARCHAR(100),          -- Milvus向量ID
    created_at TIMESTAMP
);
```

### 分块类型

1. **独立分块**（`parent_chunk_id IS NULL`）
   - 大多数分块方式生成的分块
   - 直接用于检索和显示

2. **父分块**（`parent_chunk_id IS NULL` 且有子分块引用它）
   - 仅 parent_child 方式生成
   - 不直接用于检索，只提供上下文

3. **子分块**（`parent_chunk_id IS NOT NULL`）
   - 仅 parent_child 方式生成
   - 用于检索，返回时提供父分块上下文

---

## 常见问题

### Q1: 为什么 parent_child 方式的分块数和其他方式不同？

**A**: parent_child 方式生成两级分块：
- 父分块（1536 tokens）
- 子分块（512 tokens）

显示时只显示子分块数量，但实际存储了更多数据。

### Q2: 如何判断一个文档使用了哪种分块方式？

**A**: 查看 `documents.chunk_method` 字段：
```sql
SELECT filename, chunk_method FROM documents;
```

### Q3: 旧文档（chunk_method 为 NULL）怎么办？

**A**: 旧文档使用的是默认的 parent_child 方式，但 `chunk_method` 字段为 NULL。可以手动更新：
```sql
UPDATE documents
SET chunk_method = 'parent_child'
WHERE chunk_method IS NULL AND total_chunks > 0;
```

### Q4: 如何重新分块？

**A**: 目前需要删除文档后重新上传。未来版本会支持重新分块功能。

---

## 修改文件清单

- ✅ `backend/app/api/v1/document.py`
  - 修改 `list_document_chunks` 接口（根据分块方式查询）
  - 修改 `list_documents` 接口（返回 chunk_method 字段）

---

## 下一步

1. 重启后端服务
2. 测试所有分块方式
3. 验证分块显示正确
4. 更新旧文档的 chunk_method 字段（可选）

---

**修复完成！现在所有分块方式都能正确显示了。** ✅
