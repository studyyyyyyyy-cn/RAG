<template>
  <div class="app-page">
    <div class="page-hero">
      <div>
        <p class="page-eyebrow">Quick Replay</p>
        <h2>快捷方式</h2>
        <p>把高频问答、报表与结果快照收成更醒目的彩色卡片，方便快速回看与二次导出。</p>
      </div>
      <div class="header-actions">
        <el-input v-model="search" placeholder="搜索..." prefix-icon="Search" class="search-input" clearable @input="loadShortcuts" />
        <el-switch v-model="pinnedOnly" active-text="仅置顶" @change="loadShortcuts" />
      </div>
    </div>

    <el-row :gutter="18">
      <el-col :span="8" v-for="item in shortcuts" :key="item.id">
        <ShortcutCard
          :shortcut="item"
          @delete="handleDelete"
          @pin="handlePin"
          @view="handleView"
          @export-md="() => handleExportMd(item.id)"
          @export-html="() => handleExportHtml(item.id)"
        />
      </el-col>
    </el-row>

    <el-empty v-if="shortcuts.length === 0" description="暂无快捷方式，在问答中点击保存即可添加" />

    <el-dialog v-model="showDetail" :title="detailItem?.title" width="70%" top="5vh">
      <ChatMessage v-if="detailItem" :message="{ role: 'assistant', content: detailItem.answer_snapshot, type: detailItem.answer_snapshot?.type, hideActions: true }" />
      <div class="dialog-actions" v-if="detailItem">
        <el-button v-if="!isAgentType(detailItem.answer_snapshot)" text size="small" @click="handleCopyDetail">
          <el-icon><CopyDocument /></el-icon> 复制
        </el-button>
        <el-button v-if="isReportType(detailItem.answer_snapshot)" text size="small" @click="handleExportMd(detailItem.id)">
          <el-icon><Download /></el-icon> 导出MD
        </el-button>
        <el-button v-if="isReportType(detailItem.answer_snapshot)" text size="small" @click="handleExportHtml(detailItem.id)">
          <el-icon><Download /></el-icon> 导出HTML
        </el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CopyDocument, Download } from '@element-plus/icons-vue'
import TurndownService from 'turndown'
import { shortcutApi } from '@/api'
import ChatMessage from '@/components/ChatMessage.vue'
import ShortcutCard from '@/components/ShortcutCard.vue'

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

const shortcuts = ref([])
const search = ref('')
const pinnedOnly = ref(false)
const showDetail = ref(false)
const detailItem = ref(null)

onMounted(() => loadShortcuts())

async function loadShortcuts() {
  const { data } = await shortcutApi.list({
    search: search.value || undefined,
    pinned_only: pinnedOnly.value || undefined,
  })
  shortcuts.value = data.items
}

async function handleDelete(id) {
  await ElMessageBox.confirm('确定删除此快捷方式？', '确认', { type: 'warning' })
  await shortcutApi.delete(id)
  ElMessage.success('已删除')
  loadShortcuts()
}

async function handlePin(item) {
  await shortcutApi.update(item.id, { is_pinned: !item.is_pinned })
  loadShortcuts()
}

function handleView(item) {
  detailItem.value = item
  showDetail.value = true
}

function isAgentType(snapshot) {
  if (snapshot?.type && ['report', 'chart', 'webpage', 'composite'].includes(snapshot.type)) return true
  return !!snapshot?.html_content
}

function isReportType(snapshot) {
  return snapshot?.type === 'report' || snapshot?.html_content
}

function handleCopyDetail() {
  const text = detailItem.value?.answer_snapshot?.text || ''
  navigator.clipboard.writeText(text)
  ElMessage.success('已复制')
}

function handleExportMd(id) {
  const shortcutData = shortcuts.value.find((s) => s.id === id)
  if (!shortcutData) return
  const htmlContent = shortcutData.answer_snapshot?.html_content
  if (!htmlContent) {
    ElMessage.warning('没有可导出的内容')
    return
  }
  const titleMatch = htmlContent.match(/<h[1-2][^>]*>([^<]+)<\/h[1-2]>/)
  const title = titleMatch ? titleMatch[1] : shortcutData.title
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

function handleExportHtml(id) {
  const shortcutData = shortcuts.value.find((s) => s.id === id)
  if (!shortcutData) return
  const htmlContent = shortcutData.answer_snapshot?.html_content
  if (!htmlContent) {
    ElMessage.warning('没有可导出的内容')
    return
  }
  const titleMatch = htmlContent.match(/<h[1-2][^>]*>([^<]+)<\/h[1-2]>/)
  const title = titleMatch ? titleMatch[1] : shortcutData.title
  const fullHtml = `<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>${title}</title></head><body>${htmlContent}</body></html>`
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
.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-input {
  width: 240px;
}

.dialog-actions {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #eee;
  display: flex;
  gap: 8px;
}
</style>
