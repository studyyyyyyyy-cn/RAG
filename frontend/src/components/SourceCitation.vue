<template>
  <div class="citations-list">
    <span class="citations-label">参考来源：</span>
    <el-tag
      v-for="(c, i) in citations"
      :key="i"
      size="small"
      type="info"
      class="citation-tag"
      :title="`相关度: ${(c.relevance * 100).toFixed(0)}%`"
    >
      <el-icon><Document /></el-icon>
      {{ c.source || c.doc_name || '文档' }}
      <template v-if="c.page_number"> - P{{ c.page_number }}</template>
      <template v-if="c.relevance"> ({{ (c.relevance * 100).toFixed(0) }}%)</template>
    </el-tag>
  </div>
</template>

<script setup>
defineProps({
  citations: { type: Array, required: true },
})
</script>

<style scoped>
.citations-list { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.citations-label { font-size: 12px; color: #909399; margin-right: 4px; }
.citation-tag { cursor: default; }
</style>
