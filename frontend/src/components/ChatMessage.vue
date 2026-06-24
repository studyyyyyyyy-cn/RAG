<template>
  <div class="message-bubble" :class="[message.role, isAgentContent ? 'agent-message' : '']" :data-agent-type="message.type">
    <div v-if="message.role === 'user'" class="user-bubble">
      {{ message.content?.text || message.content }}
    </div>

    <div v-else class="assistant-bubble">
      <div v-if="message.waiting" class="waiting-indicator">
        <el-icon class="loading-icon"><Loading /></el-icon>
        <span>{{ message.content?.text || '请稍候，正在处理中...' }}</span>
        <span v-if="message.showTimer !== false" class="waiting-timer">{{ waitingTimeDisplay }}</span>
      </div>

      <template v-else>
        <ConfidenceBadge v-if="message.confidence != null" :score="message.confidence" />

        <div v-if="!message.type || message.type === 'text'" class="text-content" v-html="renderedMarkdown" />

        <div v-if="message.type === 'chart'" class="agent-panel chart-panel">
          <div class="text-content" v-html="renderMd(message.content?.text || '')" />
          <div class="panel-frame">
            <ChartRenderer :option="message.content.chart_spec" />
          </div>
        </div>

        <div v-if="message.type === 'report' || (message.content?.html_content && message.type !== 'webpage')" class="agent-panel report-panel">
          <div class="panel-frame">
            <ReportViewer :html="message.content.html_content" />
          </div>
        </div>

        <div v-if="message.type === 'webpage'" class="agent-panel webpage-panel">
          <div v-if="resolvedPageUrl" class="webpage-link-card">
            <div class="webpage-link-title">{{ message.content?.page_title || '网页展示' }}</div>
            <a
              class="webpage-link"
              :href="resolvedPageUrl"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{ resolvedPageUrl }}
            </a>
            <div class="webpage-link-actions">
              <el-button type="primary" size="small" @click="openPageLink">新窗口打开</el-button>
              <el-button text size="small" @click="copyPageLink">复制链接</el-button>
            </div>
          </div>
          <div class="panel-frame">
            <WebPreview :html="message.content.html_content" />
          </div>
        </div>

        <div v-if="message.type === 'composite'" class="agent-panel composite-panel">
          <div class="text-content" v-html="renderMd(message.content?.text || '')" />
          <el-table
            v-if="message.content?.data_table?.headers?.length"
            :data="tableRows"
            size="small"
            stripe
            border
            class="table-frame"
          >
            <el-table-column
              v-for="h in message.content.data_table.headers"
              :key="h"
              :prop="h"
              :label="h"
            />
          </el-table>
          <div class="panel-frame" v-if="message.content?.chart_spec">
            <ChartRenderer :option="message.content.chart_spec" />
          </div>
          <div v-if="message.content?.insights?.length" class="insights">
            <strong>数据洞察：</strong>
            <ul>
              <li v-for="(ins, i) in message.content.insights" :key="i">{{ ins }}</li>
            </ul>
          </div>
        </div>

        <div v-if="message.content?.citations?.length" class="citations">
          <SourceCitation :citations="message.content.citations" />
        </div>

        <span v-if="streaming" class="typing-indicator">●</span>

        <div class="msg-actions" v-if="!streaming && message.role === 'assistant' && !message.hideActions">
          <el-button text size="small" @click="$emit('saveShortcut')">
            <el-icon><Star /></el-icon> 保存快捷方式
          </el-button>
          <el-button v-if="message.type !== 'report' && message.type !== 'chart' && message.type !== 'webpage'" text size="small" @click="copyText">
            <el-icon><CopyDocument /></el-icon> 复制
          </el-button>
          <el-button v-if="message.type === 'report'" text size="small" @click="exportMd">
            <el-icon><Download /></el-icon> 导出MD
          </el-button>
          <el-button v-if="message.type === 'report'" text size="small" @click="exportHtml">
            <el-icon><Download /></el-icon> 导出HTML
          </el-button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import { ElMessage } from 'element-plus'
import { CopyDocument, Download, Loading, Star } from '@element-plus/icons-vue'
import TurndownService from 'turndown'
import ChartRenderer from './ChartRenderer.vue'
import ConfidenceBadge from './ConfidenceBadge.vue'
import ReportViewer from './ReportViewer.vue'
import SourceCitation from './SourceCitation.vue'
import WebPreview from './WebPreview.vue'

const turndownService = new TurndownService({
  headingStyle: 'atx',
  codeBlockStyle: 'fenced',
  bulletListMarker: '-',
  emDelimiter: '*',
  tableHeadingsFirst: true,
})

turndownService.addRule('tables', {
  filter: 'table',
  replacement(content, node) {
    const rows = []
    node.querySelectorAll('tr').forEach((tr) => {
      const cells = []
      tr.querySelectorAll('th, td').forEach((cell) => {
        cells.push(turndownService.turndown(cell.innerHTML).trim())
      })
      if (cells.length > 0) rows.push(cells)
    })

    if (rows.length === 0) return ''

    let md = `| ${rows[0].join(' | ')} |\n`
    md += `| ${rows[0].map(() => '---').join(' | ')} |\n`
    for (let index = 1; index < rows.length; index += 1) {
      md += `| ${rows[index].join(' | ')} |\n`
    }
    return md
  },
})

const props = defineProps({
  message: { type: Object, required: true },
  streaming: { type: Boolean, default: false },
  waitingSeconds: { type: Number, default: 0 },
})

defineEmits(['saveShortcut'])

const md = new MarkdownIt({
  highlight(str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, { language: lang }).value
      } catch {}
    }
    return ''
  },
})

function renderMd(text) {
  return md.render(text || '')
}

const renderedMarkdown = computed(() => renderMd(props.message.content?.text || ''))

const waitingTimeDisplay = computed(() => {
  const secs = props.waitingSeconds || props.message.waitingSeconds || 0
  const mins = Math.floor(secs / 60)
  const s = secs % 60
  return `${mins}:${s.toString().padStart(2, '0')}`
})

const tableRows = computed(() => {
  const dt = props.message.content?.data_table
  if (!dt?.headers || !dt?.rows) return []
  return dt.rows.map((row) => {
    const obj = {}
    dt.headers.forEach((h, i) => {
      obj[h] = row[i] ?? ''
    })
    return obj
  })
})

const isAgentContent = computed(() => {
  const type = props.message.type
  const content = props.message.content
  return type === 'chart' || type === 'report' || type === 'webpage' || type === 'composite'
    || !!content?.chart_spec || !!content?.html_content || !!content?.data_table
})

const generatedPageUrl = ref('')

const rawPageUrl = computed(() => {
  const pageUrl = props.message.content?.page_url
  if (!pageUrl) return ''
  if (/^https?:\/\//i.test(pageUrl)) return pageUrl
  return `${window.location.origin}${pageUrl}`
})

const resolvedPageUrl = computed(() => generatedPageUrl.value || rawPageUrl.value)

watch(
  () => props.message.content?.html_content,
  (htmlContent) => {
    if (generatedPageUrl.value) {
      URL.revokeObjectURL(generatedPageUrl.value)
      generatedPageUrl.value = ''
    }

    if (!htmlContent || props.message.type !== 'webpage') {
      return
    }

    const fullHtml = buildStandaloneHtml(
      htmlContent,
      props.message.content?.page_title || '网页展示',
    )
    const blob = new Blob([fullHtml], { type: 'text/html;charset=utf-8' })
    generatedPageUrl.value = URL.createObjectURL(blob)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (generatedPageUrl.value) {
    URL.revokeObjectURL(generatedPageUrl.value)
  }
})

function buildStandaloneHtml(htmlContent, title) {
  if (/<html[\s>]/i.test(htmlContent)) {
    return htmlContent
  }

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title}</title>
</head>
<body>
${htmlContent}
</body>
</html>`
}

function copyText() {
  const text = props.message.content?.text || ''
  navigator.clipboard.writeText(text)
  ElMessage.success('已复制')
}

function openPageLink() {
  if (!resolvedPageUrl.value) {
    ElMessage.warning('没有可打开的网页链接')
    return
  }
  window.open(resolvedPageUrl.value, '_blank', 'noopener,noreferrer')
}

function copyPageLink() {
  if (!resolvedPageUrl.value) {
    ElMessage.warning('没有可复制的网页链接')
    return
  }
  navigator.clipboard.writeText(resolvedPageUrl.value)
  ElMessage.success('链接已复制')
}

function exportMd() {
  const htmlContent = props.message.content?.html_content
  if (!htmlContent) {
    ElMessage.warning('没有可导出的内容')
    return
  }

  const titleMatch = htmlContent.match(/<h[1-2][^>]*>([^<]+)<\/h[1-2]>/)
  const title = titleMatch ? titleMatch[1] : 'Report'
  const mdContent = turndownService.turndown(htmlContent)
  const blob = new Blob([mdContent], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${title.replace(/[^\w\u4e00-\u9fa5]/g, '_')}.md`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)

  ElMessage.success('MD导出成功')
}

function exportHtml() {
  const htmlContent = props.message.content?.html_content
  if (!htmlContent) {
    ElMessage.warning('没有可导出的内容')
    return
  }

  const titleMatch = htmlContent.match(/<h[1-2][^>]*>([^<]+)<\/h[1-2]>/)
  const title = titleMatch ? titleMatch[1] : 'Report'
  const fullHtml = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>${title}</title>
  <style>
    body { font-family: Microsoft YaHei, SimHei, sans-serif; padding: 40px; max-width: 900px; margin: 0 auto; color: #303133; }
    h1 { font-size: 24px; color: #303133; border-bottom: 2px solid #409eff; padding-bottom: 10px; }
    h2 { font-size: 18px; color: #303133; margin-top: 24px; }
    h3 { font-size: 16px; color: #606266; }
    table { width: 100%; border-collapse: collapse; margin: 16px 0; }
    th, td { border: 1px solid #dcdfe6; padding: 10px 12px; text-align: left; }
    th { background: #f5f7fa; }
    tr:nth-child(even) { background: #fafafa; }
    .summary { background: #f0f9eb; padding: 12px; border-radius: 16px; margin: 12px 0; }
    .conclusion { background: #ecf5ff; padding: 12px; border-radius: 16px; margin: 12px 0; }
    ul, ol { padding-left: 24px; }
    li { margin: 6px 0; }
  </style>
</head>
<body>${htmlContent}</body>
</html>`

  const blob = new Blob([fullHtml], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${title.replace(/[^\w\u4e00-\u9fa5]/g, '_')}.html`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)

  ElMessage.success('HTML导出成功')
}
</script>

<style scoped>
.message-bubble {
  max-width: 80%;
}

.message-bubble.agent-message,
.message-bubble[data-agent-type="chart"],
.message-bubble[data-agent-type="report"],
.message-bubble[data-agent-type="webpage"],
.message-bubble[data-agent-type="composite"] {
  max-width: 96%;
  width: 96%;
}

.user-bubble {
  padding: 14px 18px;
  border-radius: 24px 24px 8px 24px;
  background: linear-gradient(135deg, #4f7cff, #7f5af0 54%, #48dbfb);
  color: #fff;
  font-size: 14px;
  line-height: 1.7;
  box-shadow: 0 16px 28px rgba(79, 124, 255, 0.2);
}

.assistant-bubble {
  position: relative;
  min-width: 220px;
  padding: 16px 18px;
  border-radius: 24px 24px 24px 10px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 255, 0.96));
  border: 1px solid rgba(226, 231, 245, 0.94);
  box-shadow: 0 14px 34px rgba(89, 101, 147, 0.1);
}

.text-content {
  font-size: 14px;
  line-height: 1.9;
  color: #2d3550;
}

.text-content :deep(pre) {
  padding: 14px 16px;
  border-radius: 18px;
  background: linear-gradient(180deg, #f7f9ff, #eef3ff);
  overflow-x: auto;
}

.text-content :deep(code) {
  font-family: Consolas, monospace;
  font-size: 13px;
}

.text-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0;
  overflow: hidden;
  border-radius: 16px;
}

.text-content :deep(th),
.text-content :deep(td) {
  border: 1px solid #e4e9f4;
  padding: 9px 12px;
  text-align: left;
}

.text-content :deep(th) {
  background: #f3f7ff;
}

.agent-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.panel-frame {
  padding: 12px;
  border-radius: 22px;
  background: linear-gradient(135deg, rgba(247, 250, 255, 0.98), rgba(255, 248, 252, 0.98));
  border: 1px solid rgba(226, 232, 246, 0.9);
  overflow: hidden;
}

.table-frame {
  border-radius: 20px;
  overflow: hidden;
}

.table-frame :deep(.el-table) {
  border-radius: 20px;
}

.citations {
  margin-top: 14px;
  padding-top: 10px;
  border-top: 1px solid rgba(230, 233, 243, 0.96);
}

.typing-indicator {
  animation: blink 0.8s infinite;
  color: #4f7cff;
}

.msg-actions {
  margin-top: 10px;
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.msg-actions :deep(.el-button) {
  border-radius: 14px;
}

.insights {
  padding: 14px 16px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(29, 209, 161, 0.1), rgba(72, 219, 251, 0.1));
  font-size: 14px;
  color: #294057;
}

.insights ul {
  padding-left: 20px;
  margin-top: 6px;
}

.webpage-link-card {
  padding: 14px 16px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(79, 124, 255, 0.08), rgba(72, 219, 251, 0.1));
  border: 1px solid rgba(79, 124, 255, 0.16);
}

.webpage-link-title {
  margin-bottom: 8px;
  font-weight: 700;
  color: #294057;
}

.webpage-link {
  display: block;
  word-break: break-all;
  color: #2a5bd7;
  text-decoration: underline;
}

.webpage-link-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.waiting-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #69758e;
  padding: 12px 14px;
  background: linear-gradient(135deg, rgba(248, 250, 255, 0.98), rgba(255, 246, 250, 0.98));
  border-radius: 18px;
  border: 1px solid rgba(227, 231, 244, 0.96);
}

.waiting-timer {
  margin-left: 8px;
  padding: 3px 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, #4f7cff, #48dbfb);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  min-width: 42px;
  text-align: center;
}

.loading-icon {
  animation: spin 1s linear infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
