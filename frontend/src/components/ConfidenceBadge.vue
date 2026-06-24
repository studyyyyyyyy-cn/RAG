<template>
  <el-tooltip :content="tooltipText" placement="top">
    <el-tag :type="tagType" size="small" class="confidence-badge">
      {{ label }} {{ (score * 100).toFixed(0) }}%
    </el-tag>
  </el-tooltip>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  score: { type: Number, required: true },
})

const label = computed(() => {
  if (props.score >= 0.8) return '高置信度'
  if (props.score >= 0.5) return '中置信度'
  if (props.score >= 0.3) return '低置信度'
  return '极低置信度'
})

const tagType = computed(() => {
  if (props.score >= 0.8) return 'success'
  if (props.score >= 0.5) return 'warning'
  return 'danger'
})

const tooltipText = computed(() =>
  `检索置信度 ${(props.score * 100).toFixed(1)}% — ${props.score < 0.5 ? '回答可能不够准确，建议补充知识库文档' : '检索结果可信度较高'}`
)
</script>

<style scoped>
.confidence-badge { margin-bottom: 8px; }
</style>
