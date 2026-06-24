# 测试新的分块流程

## 测试步骤

### 1. 启动服务

确保前后端服务都在运行：

```bash
# 后端
cd backend
venv\Scripts\activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 前端
cd frontend
npm run dev
```

### 2. 测试上传文档

访问 `http://localhost:5173`，进入任意知识库：

1. 点击"上传文档"
2. 选择一个测试文件（如 test.txt）
3. 观察上传进度

**预期结果**：
- 上传完成后显示"✓ 上传成功，等待分块"
- 文档列表中状态显示为"待分块"
- 分块方式列显示下拉框（可选择）

### 3. 测试单个文档分块

在文档列表中：

1. 找到刚上传的文档（状态：待分块）
2. 在"分块方式"列选择一种方式（如"智能分块"）
3. 点击"执行分块"按钮
4. 等待处理完成

**预期结果**：
- 状态变为"分块中"
- 处理完成后状态变为"完成"
- 显示分块数量
- 可以点击"查看分块"查看详情

### 4. 测试批量分块

1. 上传多个文档（2-3个）
2. 勾选这些文档（checkbox）
3. 在底部批量操作栏选择分块方式
4. 点击"批量执行分块"
5. 等待处理完成

**预期结果**：
- 系统按顺序处理每个文档
- 显示成功/失败统计
- 所有文档状态更新为"完成"

### 5. 测试不同分块方式

分别测试 6 种分块方式：

| 分块方式 | 测试文件 | 预期效果 |
|---------|---------|---------|
| 智能分块 | 有章节的 Markdown 文件 | 按章节分块 |
| 问答分块 | FAQ 文档 | 每个问答对一个分块 |
| 表格分块 | 包含表格的文档 | 表格独立分块 |
| 通用分块 | 纯文本 | 固定大小分块 |
| 父子分块 | 任意文档 | 两级分块 |
| 递归分块 | 长文本 | 按分隔符递归分块 |

## API 测试

### 测试上传接口

```bash
curl -X POST "http://localhost:8000/api/v1/kb/{kb_id}/documents" \
  -F "files=@test.txt"
```

**预期响应**：
```json
{
  "uploaded": 1,
  "results": [
    {
      "id": "doc-uuid",
      "filename": "test.txt",
      "status": "parsed",
      "error_message": null
    }
  ]
}
```

### 测试单个分块接口

```bash
curl -X POST "http://localhost:8000/api/v1/kb/{kb_id}/documents/{doc_id}/chunk?chunk_method=intelligent"
```

**预期响应**：
```json
{
  "id": "doc-uuid",
  "filename": "test.txt",
  "status": "done",
  "chunk_method": "intelligent",
  "total_chunks": 15
}
```

### 测试批量分块接口

```bash
curl -X POST "http://localhost:8000/api/v1/kb/{kb_id}/documents/chunk-batch" \
  -H "Content-Type: application/json" \
  -d '{
    "doc_ids": ["doc-id-1", "doc-id-2"],
    "chunk_method": "parent_child"
  }'
```

**预期响应**：
```json
{
  "processed": 2,
  "results": [
    {
      "id": "doc-id-1",
      "filename": "doc1.txt",
      "status": "done",
      "chunk_method": "parent_child",
      "total_chunks": 20
    },
    {
      "id": "doc-id-2",
      "filename": "doc2.txt",
      "status": "done",
      "chunk_method": "parent_child",
      "total_chunks": 18
    }
  ]
}
```

## 常见问题排查

### 问题 1：上传后仍然自动分块

**检查**：
- 后端代码是否已更新
- 数据库是否已迁移
- 服务是否已重启

**解决**：
```bash
# 重启后端服务
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 问题 2：分块方式下拉框不显示

**检查**：
- 文档状态是否为"待分块"（parsed）
- 前端代码是否已更新
- 浏览器缓存是否已清除

**解决**：
- 刷新页面（Ctrl+F5）
- 检查浏览器控制台错误

### 问题 3：批量执行失败

**检查**：
- 选中的文档状态是否都是"待分块"
- 是否选择了分块方式
- 后端日志是否有错误

**解决**：
- 查看后端日志
- 检查文档状态
- 确认分块方式已选择

### 问题 4：分块数量为 0

**检查**：
- 文档内容是否为空
- 分块方式是否适合该文档
- 后端日志是否有错误

**解决**：
- 尝试其他分块方式
- 检查文档内容
- 查看错误信息

## 验证清单

- [ ] 上传文档后状态为"待分块"
- [ ] 可以选择分块方式
- [ ] 单个文档分块成功
- [ ] 批量分块成功
- [ ] 6 种分块方式都能正常工作
- [ ] 分块完成后可以查看详情
- [ ] 可以进行问答测试
- [ ] 不同文档可以使用不同分块方式

## 成功标准

✅ 所有测试步骤通过
✅ 所有 API 接口正常
✅ 前端界面显示正确
✅ 分块结果符合预期

---

**测试完成后，新功能即可正式使用！**
