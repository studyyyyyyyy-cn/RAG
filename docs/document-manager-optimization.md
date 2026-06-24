# 文档管理功能优化说明

## 优化内容

### 1. 去掉批量操作栏的分块方式选择 ✅

**优化前：**
```
批量操作栏：
[已选择 3 个文档] [分块方式下拉框] [批量执行分块按钮]
```

**优化后：**
```
批量操作栏：
[已选择 3 个文档] [批量执行分块按钮]
```

**说明：**
- 移除了批量操作栏中的分块方式选择下拉框
- 每个文档使用自己选择的分块方式
- 批量执行时，系统会按文档各自的分块方式分组执行

---

### 2. 每个文档独立选择分块方式 ✅

**功能：**
- 每个文档在"分块方式"列都有独立的下拉框
- 用户可以为不同文档选择不同的分块方式
- 只有状态为"待分块"的文档才显示下拉框

**示例：**
```
文档A.csv  → 选择"表格分块"
文档B.md   → 选择"智能分块"
文档C.txt  → 选择"通用分块"
```

---

### 3. 文档上传后默认选择通用分块 ✅

**功能：**
- 文档上传并解析成功后（状态为"待分块"）
- 系统自动为文档设置默认分块方式：**通用分块（general）**
- 用户可以随时修改为其他分块方式

**代码实现：**
```javascript
async function loadDocuments() {
  loading.value = true
  try {
    const { data } = await docApi.list(kbId, { page: page.value, page_size: pageSize })
    // 为每个文档设置默认分块方式
    documents.value = data.items.map(doc => ({
      ...doc,
      chunk_method: doc.chunk_method || (doc.parse_status === 'parsed' ? 'general' : doc.chunk_method)
    }))
    total.value = data.total
  } finally {
    loading.value = false
  }
}
```

---

### 4. 批量执行分块优化 ✅

**功能：**
- 选中多个文档后，点击"批量执行分块"
- 系统会检查每个文档是否已选择分块方式
- 如果有文档未选择分块方式，提示用户
- 按分块方式分组，分别调用批量分块API

**代码实现：**
```javascript
async function executeBatchChunk() {
  const parsedDocs = selectedDocs.value.filter(d => d.parse_status === 'parsed')

  // 检查是否所有文档都选择了分块方式
  const docsWithoutMethod = parsedDocs.filter(d => !d.chunk_method)
  if (docsWithoutMethod.length > 0) {
    ElMessage.warning('请为所有选中的文档选择分块方式')
    return
  }

  // 按分块方式分组
  const groupedDocs = {}
  parsedDocs.forEach(doc => {
    if (!groupedDocs[doc.chunk_method]) {
      groupedDocs[doc.chunk_method] = []
    }
    groupedDocs[doc.chunk_method].push(doc.id)
  })

  // 对每组执行批量分块
  for (const [method, docIds] of Object.entries(groupedDocs)) {
    await docApi.chunkBatch(kbId, docIds, method)
  }
}
```

**示例：**
```
选中3个文档：
- 文档A.csv  → 表格分块
- 文档B.md   → 智能分块
- 文档C.txt  → 智能分块

执行批量分块：
1. 调用 chunkBatch(['文档A.csv'], 'table')
2. 调用 chunkBatch(['文档B.md', '文档C.txt'], 'intelligent')
```

---

### 5. 批量执行按钮状态控制 ✅

**功能：**
- 只有当所有选中的文档都选择了分块方式时，按钮才可用
- 如果有文档未选择分块方式，按钮禁用并显示提示

**代码实现：**
```javascript
// 计算属性：是否可以批量执行
const canBatchExecute = computed(() => {
  const parsedDocs = selectedDocs.value.filter(d => d.parse_status === 'parsed')
  return parsedDocs.length > 0 && parsedDocs.every(d => d.chunk_method)
})
```

**UI显示：**
```
[批量执行分块] （按钮可用）

或

[批量执行分块] （按钮禁用） （请为每个文档选择分块方式）
```

---

## 使用流程

### 单个文档分块

1. 上传文档
2. 等待解析完成（状态变为"待分块"）
3. 系统自动设置默认分块方式为"通用分块"
4. 可以修改为其他分块方式
5. 点击"执行分块"按钮

### 批量文档分块

1. 上传多个文档
2. 等待所有文档解析完成
3. 系统自动为每个文档设置默认分块方式为"通用分块"
4. 为每个文档选择合适的分块方式（可以不同）
5. 勾选需要分块的文档
6. 点击"批量执行分块"按钮
7. 系统按分块方式分组执行

---

## 修改文件清单

1. ✅ `frontend/src/views/DocumentManager.vue`
   - 移除批量操作栏的分块方式选择
   - 添加 `canBatchExecute` 计算属性
   - 修改 `loadDocuments` 函数，设置默认分块方式
   - 修改 `executeBatchChunk` 函数，支持按分块方式分组

---

## 优势

1. **更灵活** - 每个文档可以选择最适合的分块方式
2. **更直观** - 在文档列表中直接看到每个文档的分块方式
3. **更高效** - 批量执行时自动分组，减少API调用
4. **更友好** - 默认选择通用分块，减少用户操作步骤

---

## 测试建议

### 测试场景1：单个文档
1. 上传一个CSV文件
2. 确认默认选择"通用分块"
3. 修改为"表格分块"
4. 执行分块
5. 查看分块结果

### 测试场景2：批量文档（相同分块方式）
1. 上传3个Markdown文件
2. 确认都默认选择"通用分块"
3. 全部修改为"智能分块"
4. 全选后批量执行分块
5. 确认都成功分块

### 测试场景3：批量文档（不同分块方式）
1. 上传CSV、MD、TXT各一个
2. CSV选择"表格分块"
3. MD选择"智能分块"
4. TXT保持"通用分块"
5. 全选后批量执行分块
6. 确认都按各自的方式分块

### 测试场景4：未选择分块方式
1. 上传一个文档
2. 清空分块方式选择
3. 尝试执行分块
4. 确认提示"请先选择分块方式"

---

## 注意事项

1. **默认分块方式**
   - 只对新上传的文档生效
   - 已有文档保持原有的分块方式

2. **批量执行**
   - 只处理状态为"待分块"的文档
   - 自动过滤其他状态的文档

3. **分块方式分组**
   - 相同分块方式的文档会合并为一次API调用
   - 提高批量处理效率

---

## 相关文档

- [分块策略说明](chunking-strategies.md)
- [分块优化总结](chunking-optimization-summary.md)
