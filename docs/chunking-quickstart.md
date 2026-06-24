# 多种分块方式功能 - 快速启动指南

## 1. 数据库迁移

首先需要更新数据库结构，添加新字段：

```bash
# 连接到 PostgreSQL 数据库
psql -U raguser -d ragdb

# 执行迁移脚本
\i backend/migrations/add_chunk_method.sql

# 或者直接执行 SQL
ALTER TABLE documents ADD COLUMN IF NOT EXISTS chunk_method VARCHAR(50);
UPDATE documents SET parse_status = 'parsed' WHERE parse_status = 'processing';
```

## 2. 启动服务

### 后端
```bash
cd backend
venv\Scripts\activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端
```bash
cd frontend
npm run dev
```

或者使用根目录的启动脚本：
```bash
# Windows
start.bat
```

## 3. 使用新功能

### 上传文档
1. 进入知识库管理
2. 选择一个知识库
3. 点击"上传文档"
4. 选择文件上传

**注意**：上传后文档状态为"待分块"，不会自动分块。

### 选择分块方式

在文档列表中，每个文档都有一个"分块方式"下拉框：

| 分块方式 | 适用场景 |
|---------|---------|
| 智能分块 | 技术文档、书籍（有章节结构） |
| 问答分块 | FAQ、客服文档 |
| 表格分块 | 数据报表、包含表格的文档 |
| 通用分块 | 纯文本、无明显结构 |
| 父子分块 | 通用场景（推荐，系统默认） |
| 递归分块 | 长文本、需要保持语义完整性 |

### 执行分块

**单个文档**：
1. 选择分块方式
2. 点击"执行分块"按钮
3. 等待处理完成（状态变为"完成"）

**批量执行**：
1. 勾选多个文档（checkbox）
2. 在底部批量操作栏选择分块方式
3. 点击"批量执行分块"
4. 系统按顺序处理

### 查看结果

分块完成后：
- 状态显示为"完成"
- 显示分块数量
- 点击"查看分块"可以查看详细内容

## 4. 测试示例

### 测试智能分块

创建一个测试文档 `test.md`：

```markdown
# 第一章 系统架构

## 1.1 前端架构
前端采用 Vue 3 + Vite 构建...

## 1.2 后端架构
后端采用 FastAPI + PostgreSQL...

# 第二章 数据库设计

## 2.1 表结构
系统包含以下核心表...
```

上传后选择"智能分块"，系统会按章节自动分块。

### 测试问答分块

创建 FAQ 文档 `faq.txt`：

```
Q: 如何安装系统？
A: 执行以下步骤：1. 克隆代码 2. 安装依赖 3. 启动服务

Q: 系统支持哪些功能？
A: 系统支持知识库管理、智能问答、多智能体路由等功能

Q: 如何配置 LLM？
A: 在系统设置中添加 LLM 配置，填写 API Key 和模型名称
```

上传后选择"问答分块"，每个问答对会成为一个独立分块。

## 5. API 测试

### 使用 curl 测试

```bash
# 单个文档分块
curl -X POST "http://localhost:8000/api/v1/kb/{kb_id}/documents/{doc_id}/chunk?chunk_method=intelligent"

# 批量分块
curl -X POST "http://localhost:8000/api/v1/kb/{kb_id}/documents/chunk-batch?chunk_method=parent_child" \
  -H "Content-Type: application/json" \
  -d '{"doc_ids": ["doc-id-1", "doc-id-2"]}'
```

### 使用前端 API 测试页面

访问 `http://localhost:5173/api-test` 可以测试所有 API 接口。

## 6. 常见问题

### Q: 上传后为什么不自动分块？

**A**: 这是新功能的设计，允许用户选择最合适的分块方式。如果需要自动分块，可以在上传后立即执行批量分块。

### Q: 如何处理已有的文档？

**A**: 已有文档的状态可能是"完成"，如果需要重新分块：
1. 删除文档
2. 重新上传
3. 选择新的分块方式

### Q: 批量执行会阻塞吗？

**A**: 批量执行是同步的，会按顺序处理每个文档。建议分批处理大量文档。

### Q: 不同分块方式可以混用吗？

**A**: 可以！每个文档可以使用不同的分块方式，系统会正确处理。

## 7. 性能建议

- **小文档（<10页）**：任何方式都可以
- **中等文档（10-50页）**：推荐父子分块或智能分块
- **大文档（>50页）**：推荐递归分块或通用分块
- **批量处理**：建议每批不超过 20 个文档

## 8. 下一步

- 查看详细文档：`docs/chunking-methods.md`
- 查看分块策略对比：`docs/chunking-strategies.md`
- 查看功能对比：`docs/feature-comparison.md`

## 9. 反馈和支持

如有问题或建议，请提交 Issue 或联系开发团队。

---

**祝使用愉快！** 🎉
