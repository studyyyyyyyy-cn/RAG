# 混合检索实现说明

## 概述

系统已实现完整的混合检索（Hybrid Search）功能，结合密集向量（Dense）和稀疏向量（Sparse）检索，使用RRF（Reciprocal Rank Fusion）算法融合结果，显著提升检索准确性。

## 实现方案

### 1. 向量存储增强

**InMemoryVectorStore** 已支持：
- 存储稀疏向量（sparse_vectors）
- 稀疏向量检索（sparse_search）
- 混合检索与RRF融合（hybrid_search）

### 2. RRF融合算法

```python
# RRF公式：score = 1 / (k + rank)
# k = 60（标准RRF常数）
# 将dense和sparse的RRF分数相加得到最终分数
```

### 3. 自动切换机制

系统会自动检测Milvus Lite是否可用：
- **Milvus Lite可用**：使用Milvus的原生向量检索（当前仅支持dense）
- **Milvus Lite不可用**：使用InMemoryVectorStore的混合检索（dense + sparse + RRF）

## 测试结果

### 查询："智能吸顶灯"

**混合检索（Dense + Sparse + RRF）**：
1. 智能吸顶灯 - RRF评分: 0.0328 ✓
2. 智能灯带 - RRF评分: 0.0320
3. 智能筒灯 - RRF评分: 0.0320

**纯Dense检索**：
1. 智能吸顶灯 - Dense评分: 0.8336 ✓
2. 智能灯带 - Dense评分: 0.6219
3. 智能筒灯 - Dense评分: 0.5970

**纯Sparse检索**：
1. 智能吸顶灯 - Sparse评分: 0.2658 ✓
2. 智能筒灯 - Sparse评分: 0.1380
3. 智能灯带 - Sparse评分: 0.1350

## 优势

1. **精确匹配**：稀疏向量提供关键词精确匹配能力
2. **语义理解**：密集向量提供语义相似度匹配
3. **最佳融合**：RRF算法综合两种检索的优势
4. **自动降级**：Milvus不可用时自动使用内存版本

## 使用说明

### 前提条件

系统需要使用BGE-M3模型（支持dense + sparse向量）：
- 默认配置已启用BGE-M3
- 如设置了`USE_LIGHTWEIGHT_EMBEDDER=1`，需要移除该配置

### 重新索引

旧的向量数据不包含稀疏向量，需要重新分块：
1. 删除旧向量数据：`rm backend/data/vectors.json`
2. 在前端重新对文档进行分块操作
3. 系统会自动使用BGE-M3生成dense + sparse向量

### API调用

```python
# 后端API会自动使用混合检索
results = vector_store.hybrid_search(
    kb_id=kb_id,
    dense_query=dense_vector,
    sparse_query=sparse_vector,  # BGE-M3自动生成
    top_k=10
)
```

## 性能对比

| 检索方式 | 精确匹配 | 语义理解 | 综合效果 |
|---------|---------|---------|---------|
| Dense only | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Sparse only | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| Hybrid (RRF) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

## 技术细节

### 稀疏向量格式

```python
{
    "token_id_1": weight_1,
    "token_id_2": weight_2,
    ...
}
```

### RRF实现

```python
def hybrid_search(dense_query, sparse_query, top_k):
    # 1. 获取dense候选（top_k * 2）
    dense_results = dense_search(dense_query, top_k * 2)

    # 2. 获取sparse候选（top_k * 2）
    sparse_results = sparse_search(sparse_query, top_k * 2)

    # 3. RRF融合
    k = 60
    rrf_scores = {}
    for rank, result in enumerate(dense_results, 1):
        rrf_scores[chunk_id] += 1 / (k + rank)
    for rank, result in enumerate(sparse_results, 1):
        rrf_scores[chunk_id] += 1 / (k + rank)

    # 4. 按RRF分数排序返回top_k
    return sorted(rrf_scores, reverse=True)[:top_k]
```

## 未来优化

1. **Milvus Lite集成**：安装milvus-lite后自动使用原生混合检索
2. **权重调整**：支持调整dense和sparse的权重比例
3. **查询扩展**：支持查询改写和同义词扩展
4. **缓存优化**：缓存常见查询的向量表示

## 相关文件

- `backend/app/core/vector_store.py` - 向量存储和混合检索实现
- `backend/app/core/embedder.py` - BGE-M3嵌入模型
- `test_bge_m3_hybrid.py` - 混合检索测试脚本
