<template>
  <div class="web-preview-wrapper">
    <div class="preview-header">
      <span>网页预览</span>
      <el-button text size="small" @click="openInNewTab">在新窗口打开</el-button>
    </div>
    <iframe
      ref="iframeRef"
      :srcdoc="html"
      sandbox="allow-scripts allow-same-origin"
      class="preview-iframe"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  html: { type: String, required: true },
})

const iframeRef = ref(null)

function openInNewTab() {
  const win = window.open('', '_blank')
  win.document.write(props.html)
  win.document.close()
}
</script>

<style scoped>
.web-preview-wrapper { margin: 12px 0; border: 1px solid #e4e7ed; border-radius: 8px; overflow: hidden; }
.preview-header { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: #f5f7fa; border-bottom: 1px solid #e4e7ed; font-size: 13px; color: #606266; }
.preview-iframe { width: 100%; height: 500px; border: none; }
</style>
