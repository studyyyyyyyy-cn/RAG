<template>
  <div class="report-wrapper">
    <div v-html="html" class="report-content" />
  </div>
</template>

<script setup>
defineProps({
  html: { type: String, required: true },
})
</script>

<style scoped>
.report-wrapper { margin: 12px 0; border: 1px solid #e4e7ed; border-radius: 8px; padding: 20px; background: #fff; overflow: auto; max-height: 600px; }
.report-content :deep(table) { width: 100%; border-collapse: collapse; margin: 10px 0; }
.report-content :deep(th), .report-content :deep(td) { border: 1px solid #ddd; padding: 8px 12px; }
.report-content :deep(th) { background: #f8f9fa; font-weight: 600; }
.report-content :deep(tr:nth-child(even)) { background: #f9fafb; }
.report-content :deep(h2) { color: #303133; border-bottom: 2px solid #409eff; padding-bottom: 8px; margin-top: 20px; }
</style>
