<template>
  <div class="dashboard-page">
    <div class="hero-panel">
      <div>
        <p class="eyebrow">Data Canvas</p>
        <h2 class="page-title">数据看板</h2>
        <p class="page-subtitle">用更鲜活的颜色和更柔和的圆角，把知识库、对话与快捷方式的动态浓缩到一个面板里。</p>
      </div>
      <div class="hero-orbs">
        <span class="orb orb-a"></span>
        <span class="orb orb-b"></span>
        <span class="orb orb-c"></span>
      </div>
    </div>

    <el-row :gutter="18" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card coral">
          <div class="stat-icon">KB</div>
          <el-statistic title="知识库数量" :value="stats.kbCount" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card aqua">
          <div class="stat-icon">DOC</div>
          <el-statistic title="文档总数" :value="stats.docCount" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card violet">
          <div class="stat-icon">CHAT</div>
          <el-statistic title="对话总数" :value="stats.convCount" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card amber">
          <div class="stat-icon">SC</div>
          <el-statistic title="快捷方式" :value="stats.shortcutCount" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="18" class="content-row">
      <el-col :span="12">
        <el-card class="panel-card chart-panel">
          <template #header>
            <div class="panel-header">
              <span>知识库文档分布</span>
              <span class="panel-chip">彩色图谱</span>
            </div>
          </template>
          <div class="chart-shell">
            <v-chart :option="kbChartOption" autoresize style="height: 350px" />
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="panel-card">
          <template #header>
            <div class="panel-header">
              <span>最近对话活动</span>
              <span class="panel-chip sky">实时回顾</span>
            </div>
          </template>
          <div class="recent-list">
            <el-empty v-if="recentConversations.length === 0" description="暂无对话记录" />
            <div v-for="conv in recentConversations" :key="conv.id" class="recent-item">
              <div>
                <div class="recent-title">{{ conv.title }}</div>
                <div class="recent-meta">对话轨迹</div>
              </div>
              <el-tag size="small" effect="dark" round class="time-tag">{{ formatDate(conv.created_at) }}</el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="18" class="content-row">
      <el-col :span="24">
        <el-card class="panel-card">
          <template #header>
            <div class="panel-header">
              <span>最新快捷方式</span>
              <span class="panel-chip mint">一键回放</span>
            </div>
          </template>
          <el-empty v-if="recentShortcuts.length === 0" description="暂无快捷方式" />
          <el-row v-else :gutter="16">
            <el-col v-for="sc in recentShortcuts" :key="sc.id" :span="4">
              <div class="shortcut-card" @click="viewShortcut(sc)">
                <div class="shortcut-accent"></div>
                <div class="shortcut-title">{{ sc.title }}</div>
                <div class="shortcut-time">{{ formatDate(sc.created_at) }}</div>
              </div>
            </el-col>
          </el-row>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="showDetail" :title="detailItem?.title" width="70%" top="5vh" class="detail-dialog">
      <ChatMessage
        v-if="detailItem"
        :message="{ role: 'assistant', content: detailItem.answer_snapshot, type: detailItem.answer_snapshot?.type, hideActions: true }"
      />
      <div class="dialog-actions" v-if="detailItem">
        <el-button v-if="!isAgentType(detailItem.answer_snapshot)" text size="small" @click="handleCopyDetail">
          <el-icon><CopyDocument /></el-icon> 复制
        </el-button>
        <el-button v-if="isReportType(detailItem.answer_snapshot)" text size="small" @click="handleExportMd">
          <el-icon><Download /></el-icon> 导出MD
        </el-button>
        <el-button v-if="isReportType(detailItem.answer_snapshot)" text size="small" @click="handleExportHtml">
          <el-icon><Download /></el-icon> 导出HTML
        </el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { LegendComponent, TitleComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { ElMessage } from 'element-plus'
import { CopyDocument, Download } from '@element-plus/icons-vue'
import TurndownService from 'turndown'
import { chatApi, kbApi, shortcutApi } from '@/api'
import ChatMessage from '@/components/ChatMessage.vue'

use([PieChart, TitleComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const turndownService = new TurndownService({
  headingStyle: 'atx',
  codeBlockStyle: 'fenced',
  bulletListMarker: '-',
  emDelimiter: '*',
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

const stats = ref({ kbCount: 0, docCount: 0, convCount: 0, shortcutCount: 0 })
const kbData = ref([])
const recentConversations = ref([])
const recentShortcuts = ref([])
const showDetail = ref(false)
const detailItem = ref(null)

const kbChartOption = computed(() => ({
  backgroundColor: 'transparent',
  color: ['#ff6b6b', '#feca57', '#48dbfb', '#5f27cd', '#1dd1a1', '#ff9ff3', '#54a0ff'],
  tooltip: {
    trigger: 'item',
    backgroundColor: 'rgba(20, 24, 38, 0.88)',
    borderWidth: 0,
    textStyle: { color: '#fff' },
  },
  legend: {
    orient: 'vertical',
    left: 'left',
    top: 'middle',
    textStyle: { color: '#4b5563' },
    icon: 'roundRect',
  },
  series: [{
    type: 'pie',
    radius: ['42%', '72%'],
    center: ['62%', '50%'],
    padAngle: 2,
    itemStyle: {
      borderRadius: 18,
      borderColor: '#fff',
      borderWidth: 4,
    },
    label: {
      color: '#374151',
      formatter: '{b}\n{d}%',
      fontWeight: 600,
    },
    data: kbData.value.map((kb) => ({ value: kb.doc_count || 0, name: kb.name })),
    emphasis: {
      scale: true,
      itemStyle: {
        shadowBlur: 28,
        shadowColor: 'rgba(80, 78, 160, 0.28)',
      },
    },
  }],
}))

onMounted(async () => {
  try {
    const [kbRes, convRes, scRes] = await Promise.all([
      kbApi.list({ page_size: 100 }),
      chatApi.conversations({ page_size: 8 }),
      shortcutApi.list({ page_size: 6 }),
    ])
    kbData.value = kbRes.data.items
    stats.value.kbCount = kbRes.data.total
    stats.value.docCount = kbRes.data.items.reduce((sum, kb) => sum + (kb.doc_count || 0), 0)
    stats.value.convCount = convRes.data.total
    stats.value.shortcutCount = scRes.data.total
    recentConversations.value = convRes.data.items
    recentShortcuts.value = scRes.data.items
  } catch {}
})

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN')
}

function viewShortcut(item) {
  detailItem.value = item
  showDetail.value = true
}

function isAgentType(snapshot) {
  if (snapshot?.type && ['report', 'chart', 'webpage', 'composite'].includes(snapshot.type)) {
    return true
  }
  if (snapshot?.html_content) {
    return true
  }
  return false
}

function isReportType(snapshot) {
  return snapshot?.type === 'report' || snapshot?.html_content
}

function handleCopyDetail() {
  const text = detailItem.value?.answer_snapshot?.text || ''
  navigator.clipboard.writeText(text)
  ElMessage.success('已复制')
}

function handleExportMd() {
  const htmlContent = detailItem.value?.answer_snapshot?.html_content
  if (!htmlContent) {
    ElMessage.warning('没有可导出的内容')
    return
  }
  const titleMatch = htmlContent.match(/<h[1-2][^>]*>([^<]+)<\/h[1-2]>/)
  const title = titleMatch ? titleMatch[1] : detailItem.value?.title || 'Report'
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

function handleExportHtml() {
  const htmlContent = detailItem.value?.answer_snapshot?.html_content
  if (!htmlContent) {
    ElMessage.warning('没有可导出的内容')
    return
  }
  const titleMatch = htmlContent.match(/<h[1-2][^>]*>([^<]+)<\/h[1-2]>/)
  const title = titleMatch ? titleMatch[1] : detailItem.value?.title || 'Report'
  const fullHtml = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>${title}</title>
  <style>
    body { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; padding: 40px; max-width: 900px; margin: 0 auto; color: #303133; }
    h1 { font-size: 24px; color: #303133; border-bottom: 2px solid #409eff; padding-bottom: 10px; }
    h2 { font-size: 18px; color: #303133; margin-top: 24px; }
    h3 { font-size: 16px; color: #606266; }
    table { width: 100%; border-collapse: collapse; margin: 16px 0; }
    th, td { border: 1px solid #dcdfe6; padding: 10px 12px; text-align: left; }
    th { background: #f5f7fa; color: #303133; }
    tr:nth-child(even) { background: #fafafa; }
    .summary { background: #f0f9eb; padding: 12px; border-radius: 14px; margin: 12px 0; }
    .conclusion { background: #ecf5ff; padding: 12px; border-radius: 14px; margin: 12px 0; }
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
.dashboard-page {
  min-height: 100%;
  padding: 24px;
  background:
    radial-gradient(circle at top left, rgba(255, 107, 107, 0.16), transparent 28%),
    radial-gradient(circle at top right, rgba(72, 219, 251, 0.16), transparent 24%),
    linear-gradient(180deg, #fff8f4 0%, #f7fbff 48%, #f7fff9 100%);
}

.hero-panel {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 28px 30px;
  margin-bottom: 22px;
  border-radius: 30px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.92), rgba(245, 250, 255, 0.88));
  border: 1px solid rgba(255, 255, 255, 0.78);
  box-shadow: 0 22px 60px rgba(68, 95, 168, 0.12);
  position: relative;
  overflow: hidden;
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #ff7a59;
  font-weight: 700;
}

.page-title {
  margin: 0;
  font-size: 34px;
  line-height: 1.1;
  color: #1f2a44;
}

.page-subtitle {
  max-width: 620px;
  margin: 12px 0 0;
  color: #5b6477;
  line-height: 1.8;
}

.hero-orbs {
  position: relative;
  width: 180px;
  min-height: 120px;
}

.orb {
  position: absolute;
  border-radius: 999px;
  filter: blur(0.4px);
}

.orb-a {
  width: 120px;
  height: 120px;
  top: 8px;
  right: 18px;
  background: linear-gradient(135deg, rgba(255, 107, 107, 0.88), rgba(254, 202, 87, 0.72));
}

.orb-b {
  width: 82px;
  height: 82px;
  top: 46px;
  left: 22px;
  background: linear-gradient(135deg, rgba(72, 219, 251, 0.84), rgba(84, 160, 255, 0.8));
}

.orb-c {
  width: 52px;
  height: 52px;
  top: 10px;
  left: 78px;
  background: linear-gradient(135deg, rgba(29, 209, 161, 0.9), rgba(95, 39, 205, 0.72));
}

.stat-cards {
  margin-bottom: 4px;
}

.stat-card {
  border: 0;
  border-radius: 26px;
  overflow: hidden;
  box-shadow: 0 18px 44px rgba(84, 96, 142, 0.12);
}

.stat-card :deep(.el-card__body) {
  min-height: 152px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 22px;
}

.stat-card :deep(.el-statistic) {
  text-align: left;
}

.stat-card :deep(.el-statistic__head) {
  color: rgba(29, 34, 56, 0.68);
  font-weight: 600;
}

.stat-card :deep(.el-statistic__content) {
  color: #1f2a44;
  font-size: 30px;
}

.stat-icon {
  width: 52px;
  height: 52px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 18px;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #fff;
  box-shadow: 0 10px 22px rgba(43, 48, 78, 0.16);
}

.stat-card.coral {
  background: linear-gradient(145deg, #fff3f1, #ffffff);
}

.stat-card.coral .stat-icon {
  background: linear-gradient(135deg, #ff6b6b, #ff9f68);
}

.stat-card.aqua {
  background: linear-gradient(145deg, #eefcff, #ffffff);
}

.stat-card.aqua .stat-icon {
  background: linear-gradient(135deg, #48dbfb, #54a0ff);
}

.stat-card.violet {
  background: linear-gradient(145deg, #f3efff, #ffffff);
}

.stat-card.violet .stat-icon {
  background: linear-gradient(135deg, #7f5af0, #b16cea);
}

.stat-card.amber {
  background: linear-gradient(145deg, #fff8e9, #ffffff);
}

.stat-card.amber .stat-icon {
  background: linear-gradient(135deg, #feca57, #ff9f43);
}

.content-row {
  margin-top: 20px;
}

.content-row :deep(.el-col) {
  display: flex;
}

.panel-card {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  border-radius: 28px;
  border: 0;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 20px 54px rgba(79, 90, 133, 0.12);
}

.panel-card :deep(.el-card__header) {
  border-bottom: 0;
  padding: 22px 24px 8px;
}

.panel-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 10px 24px 24px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  font-weight: 700;
  color: #27324e;
}

.panel-chip {
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  color: #fff;
  background: linear-gradient(135deg, #ff8a5b, #ffb347);
}

.panel-chip.sky {
  background: linear-gradient(135deg, #48dbfb, #5f7bff);
}

.panel-chip.mint {
  background: linear-gradient(135deg, #1dd1a1, #10ac84);
}

.chart-shell {
  padding: 16px;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(249, 251, 255, 0.96), rgba(245, 250, 255, 0.92));
}

.recent-list {
  flex: 1;
  min-height: 350px;
  overflow: auto;
  padding-right: 4px;
}

.recent-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
  padding: 16px 18px;
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(247, 249, 255, 0.95), rgba(255, 247, 251, 0.95));
  border: 1px solid rgba(223, 229, 250, 0.8);
}

.recent-title {
  color: #2c3553;
  font-weight: 600;
}

.recent-meta {
  margin-top: 6px;
  font-size: 12px;
  color: #8a93a8;
}

.time-tag {
  border: 0;
  background: linear-gradient(135deg, #6c8cff, #63d2ff) !important;
}

.shortcut-card {
  position: relative;
  min-height: 140px;
  padding: 18px 18px 16px;
  border-radius: 24px;
  background: linear-gradient(135deg, #ffffff, #f7fbff);
  border: 1px solid rgba(224, 231, 255, 0.88);
  cursor: pointer;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
  overflow: hidden;
}

.shortcut-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 18px 38px rgba(78, 103, 171, 0.14);
}

.shortcut-accent {
  width: 58px;
  height: 8px;
  border-radius: 999px;
  margin-bottom: 18px;
  background: linear-gradient(135deg, #ff6b6b, #48dbfb, #1dd1a1);
}

.shortcut-title {
  line-height: 1.7;
  color: #27324e;
  font-weight: 600;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.shortcut-time {
  position: absolute;
  left: 18px;
  bottom: 16px;
  font-size: 12px;
  color: #8c95a8;
}

.dialog-actions {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid rgba(225, 229, 240, 0.9);
  display: flex;
  gap: 10px;
}

.detail-dialog :deep(.el-dialog) {
  border-radius: 28px;
  overflow: hidden;
}

@media (max-width: 1100px) {
  .hero-panel {
    flex-direction: column;
  }

  .hero-orbs {
    width: 100%;
    height: 100px;
  }
}
</style>
