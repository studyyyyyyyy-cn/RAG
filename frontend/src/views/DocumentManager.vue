<template>
  <div class="doc-management">
    <el-card class="header-card">
      <div class="header-content">
        <div class="title-section">
          <el-button :icon="ArrowLeft" @click="backToList" circle />
          <h2>{{ kbName ? `${kbName} / 文档管理` : '文档管理' }}</h2>
        </div>
        <div class="actions">
          <el-button type="info" :icon="QuestionFilled" @click="showMethodInfoDialog = true">
            分块方式说明
          </el-button>
          <FileUploader :kb-id="kbId" @uploaded="loadDocuments" />
          <el-button
            type="success"
            :icon="Operation"
            :disabled="selectedDocs.length === 0"
            :loading="chunking"
            @click="executeBatchChunking"
          >
            批量分块 ({{ selectedDocs.length }})
          </el-button>
          <el-button
            type="danger"
            :icon="Delete"
            :disabled="selectedDocs.length === 0"
            @click="batchDelete"
          >
            批量删除
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card>
      <el-table :data="documents" v-loading="loading" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="55" />
        <el-table-column label="文档名称" min-width="250">
          <template #default="{ row }">
            <div class="doc-name-cell">
              <span class="doc-name">{{ row.name }}</span>
              <el-tag :type="getFormatType(row.file_format)" size="small" class="format-tag">
                {{ (row.file_format || 'txt').toUpperCase() }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="upload_time" label="上传时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.upload_time) }}
          </template>
        </el-table-column>
        <el-table-column prop="file_size" label="文件大小" width="120">
          <template #default="{ row }">
            {{ formatSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="chunk_status" label="分块状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.chunk_status)">
              {{ getStatusText(row.chunk_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="分块数量" width="100">
          <template #default="{ row }">
            {{ row.chunk_count || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="分块方式" width="250">
          <template #default="{ row }">
            <div v-if="row.chunk_status === 'not_chunked'">
              <el-select v-model="row.selected_method" placeholder="选择分块方式" size="small" style="width: 100%">
                <el-option
                  v-for="method in chunkMethods"
                  :key="method.value"
                  :label="method.name"
                  :value="method.value"
                />
              </el-select>
            </div>
            <div v-else-if="row.chunk_status === 'chunking'" class="chunking-status">
              <el-progress :percentage="row.chunk_progress || 0" :stroke-width="6" />
              <span class="progress-text">{{ getMethodText(row.chunk_method) }} - 处理中...</span>
            </div>
            <span v-else>{{ getMethodText(row.chunk_method) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.chunk_status === 'not_chunked'"
              link
              type="success"
              :disabled="!row.selected_method"
              @click="executeChunkingSingle(row)"
            >
              执行分块
            </el-button>
            <el-button v-else-if="row.chunk_status === 'chunked'" link type="primary" @click="viewChunks(row)">
              查看
            </el-button>
            <el-button v-else-if="row.chunk_status === 'chunking'" link type="info" disabled>
              处理中
            </el-button>
            <el-button link type="danger" @click="deleteDoc(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="showParamsDialog"
      :title="currentDoc ? '设置分块参数' : '批量分块参数设置'"
      width="500px"
    >
      <el-form :model="chunkParams" label-width="140px">
        <el-form-item label="关键词提取数量">
          <el-input-number v-model="chunkParams.keyword_count" :min="1" :max="20" :step="1" />
          <div class="form-tip">每个分块提取的关键词数量</div>
        </el-form-item>
        <el-form-item label="生成问题数量">
          <el-input-number v-model="chunkParams.question_count" :min="1" :max="10" :step="1" />
          <div class="form-tip">为每个分块生成的问题数量</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showParamsDialog = false">取消</el-button>
        <el-button type="primary" :loading="chunking" @click="currentDoc ? confirmChunkingSingle() : confirmBatchChunking()">
          确定分块
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showMethodInfoDialog" title="分块方式说明" width="900px">
      <div class="method-info-container">
        <el-card v-for="method in chunkMethods" :key="method.value" class="method-info-card" shadow="hover">
          <template #header>
            <div class="method-header">
              <span class="method-name">{{ method.name }}</span>
              <el-tag type="primary" size="small">{{ method.value }}</el-tag>
            </div>
          </template>
          <div class="method-info-content">
            <div class="info-item">
              <span class="info-label">适用场景：</span>
              <span class="info-text scenario-text">{{ method.scenario }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">说明：</span>
              <span class="info-text">{{ method.description }}</span>
            </div>
            <div class="info-item pros-item">
              <span class="info-label">优点：</span>
              <span class="info-text">{{ method.pros }}</span>
            </div>
            <div class="info-item cons-item">
              <span class="info-label">缺点：</span>
              <span class="info-text">{{ method.cons }}</span>
            </div>
          </div>
        </el-card>
      </div>
    </el-dialog>

    <el-dialog v-model="showChunksDialog" title="分块结果" width="calc(100vw - 200px)" top="100px">
      <el-table :data="chunks" :max-height="chunkDialogTableHeight">
        <el-table-column prop="chunk_index" label="序号" width="80" />
        <el-table-column prop="content" label="内容" min-width="300">
          <template #default="{ row }">
            <div class="chunk-content">{{ row.content }}</div>
          </template>
        </el-table-column>
        <el-table-column label="关键词" width="220">
          <template #default="{ row }">
            <div v-if="row.keywords">
              <el-tag v-for="(keyword, idx) in safeParseArray(row.keywords)" :key="idx" size="small" style="margin: 2px">
                {{ keyword }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="生成问题" width="320">
          <template #default="{ row }">
            <div v-if="row.questions" class="questions-list">
              <div v-for="(question, idx) in safeParseArray(row.questions)" :key="idx" class="question-item">
                {{ idx + 1 }}. {{ question }}
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="元数据" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.metadata">{{ safeParseObject(row.metadata).type || '通用' }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Delete, Operation, QuestionFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { docApi, kbApi } from '@/api'
import FileUploader from '@/components/FileUploader.vue'

const route = useRoute()
const router = useRouter()
const kbId = route.params.id

const kbName = ref('')
const documents = ref([])
const selectedDocs = ref([])
const loading = ref(false)
const showChunksDialog = ref(false)
const showMethodInfoDialog = ref(false)
const showParamsDialog = ref(false)
const chunking = ref(false)
const chunks = ref([])
const currentDoc = ref(null)
const viewportHeight = ref(typeof window !== 'undefined' ? window.innerHeight : 900)
const chunkDialogTableHeight = computed(() => Math.max(viewportHeight.value - 260, 320))
const chunkParams = ref({
  keyword_count: 5,
  question_count: 3,
})

const chunkMethods = [
  {
    value: 'naive',
    name: '朴素分块',
    scenario: '适用场景：简单文档、通用文本',
    description: '按固定长度切分，支持重叠区域，最简单快速的分块方式',
    pros: '实现简单，处理速度快，适用于大多数文本场景',
    cons: '可能在句子或段落中间切断，不考虑文档语义结构',
  },
  {
    value: 'general',
    name: '通用分块',
    scenario: '适用场景：结构化文档、技术文档',
    description: '智能识别段落与自然边界，按语义单元切分',
    pros: '保持段落完整性，适合有明确结构的文档',
    cons: '对文档格式有一定要求',
  },
  {
    value: 'book',
    name: '书籍分块',
    scenario: '适用场景：书籍、长篇文档、学术资料',
    description: '识别章节、标题层级，按书籍结构进行分块',
    pros: '保留文档层级结构，适合长文档和书籍',
    cons: '需要较明确的章节标记',
  },
  {
    value: 'paper',
    name: '论文分块',
    scenario: '适用场景：学术论文、研究报告',
    description: '识别摘要、引言、方法、结论等论文结构',
    pros: '针对论文结构优化，保留学术逻辑性',
    cons: '仅适用于标准论文格式',
  },
  {
    value: 'resume',
    name: '简历分块',
    scenario: '适用场景：简历、个人档案',
    description: '识别教育经历、工作经验、技能等简历模块',
    pros: '针对简历结构优化，便于信息提取',
    cons: '仅适用于简历类文档',
  },
  {
    value: 'table',
    name: '表格分块',
    scenario: '适用场景：包含大量表格的文档',
    description: '保留表格结构，把每行数据转成更易检索的内容',
    pros: '保持表格数据完整性，利于结构化检索',
    cons: '依赖表格识别质量',
  },
  {
    value: 'qa',
    name: '问答分块',
    scenario: '适用场景：FAQ 文档、问答知识库',
    description: '识别问题与答案配对，适合直接问答检索',
    pros: '天然适配问答场景，检索命中率高',
    cons: '仅适用于问答格式内容',
  },
]

let progressPollingTimer = null

function updateViewportHeight() {
  viewportHeight.value = window.innerHeight
}

onMounted(async () => {
  updateViewportHeight()
  window.addEventListener('resize', updateViewportHeight)
  try {
    const { data } = await kbApi.get(kbId)
    kbName.value = data.name || ''
  } catch {
    kbName.value = ''
  }
  loadDocuments()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateViewportHeight)
  stopProgressPolling()
})

async function loadDocuments() {
  loading.value = true
  try {
    const { data } = await docApi.list(kbId, { page: 1, page_size: 100 })
    documents.value = (data.items || []).map((doc) => ({
      ...doc,
      selected_method: doc.chunk_method || null,
    }))

    const chunkingDocs = documents.value.filter((doc) => doc.chunk_status === 'chunking')
    if (chunkingDocs.length > 0) {
      startProgressPolling(chunkingDocs.map((doc) => doc.id))
    } else {
      stopProgressPolling()
    }
  } catch (error) {
    ElMessage.error('加载文档列表失败')
  } finally {
    loading.value = false
  }
}

function handleSelectionChange(selection) {
  selectedDocs.value = selection
}

function startProgressPolling(docIds) {
  stopProgressPolling()

  progressPollingTimer = setInterval(async () => {
    let allCompleted = true

    for (const docId of docIds) {
      try {
        const { data } = await docApi.status(kbId, docId)
        const doc = documents.value.find((item) => item.id === docId)

        if (doc) {
          doc.chunk_status = data.status
          doc.chunk_progress = data.progress
          doc.chunk_count = data.total_chunks
          doc.total_chunks = data.total_chunks
          if (data.status === 'chunked') {
            doc.chunk_method = doc.selected_method || doc.chunk_method
          }
          if (data.status === 'chunking') {
            allCompleted = false
          }
        }
      } catch (error) {
        console.error('获取分块进度失败', error)
      }
    }

    if (allCompleted) {
      stopProgressPolling()
      loadDocuments()
    }
  }, 1000)
}

function stopProgressPolling() {
  if (progressPollingTimer) {
    clearInterval(progressPollingTimer)
    progressPollingTimer = null
  }
}

function executeChunkingSingle(doc) {
  if (!doc.selected_method) {
    ElMessage.warning('请先选择分块方式')
    return
  }
  currentDoc.value = doc
  showParamsDialog.value = true
}

async function confirmChunkingSingle() {
  if (!currentDoc.value) return
  chunking.value = true
  try {
    currentDoc.value.chunk_status = 'chunking'
    currentDoc.value.chunk_progress = 0

    const { data } = await docApi.chunkBatch(
      kbId,
      [currentDoc.value.id],
      currentDoc.value.selected_method,
      chunkParams.value,
    )

    showParamsDialog.value = false

    const result = data.results?.[0]
    if (result?.success) {
      startProgressPolling([currentDoc.value.id])
      ElMessage.success('分块任务已启动')
    } else {
      currentDoc.value.chunk_status = 'not_chunked'
      currentDoc.value.chunk_progress = 0
      ElMessage.error(`分块失败: ${result?.error_message || result?.detail || '未知错误'}`)
    }
  } catch (error) {
    currentDoc.value.chunk_status = 'not_chunked'
    currentDoc.value.chunk_progress = 0
    ElMessage.error(`分块失败: ${error.response?.data?.detail || error.message}`)
  } finally {
    chunking.value = false
  }
}

function executeBatchChunking() {
  const notChunkedDocs = selectedDocs.value.filter((doc) => doc.chunk_status === 'not_chunked')
  if (notChunkedDocs.length === 0) {
    ElMessage.warning('没有可分块的文档')
    return
  }

  const docsWithoutMethod = notChunkedDocs.filter((doc) => !doc.selected_method)
  if (docsWithoutMethod.length > 0) {
    ElMessage.warning(`有 ${docsWithoutMethod.length} 个文档未选择分块方式，请先选择分块方式`)
    return
  }

  currentDoc.value = null
  showParamsDialog.value = true
}

async function confirmBatchChunking() {
  const notChunkedDocs = selectedDocs.value.filter((doc) => doc.chunk_status === 'not_chunked')
  chunking.value = true

  try {
    notChunkedDocs.forEach((doc) => {
      doc.chunk_status = 'chunking'
      doc.chunk_progress = 0
    })

    const results = []
    for (const doc of notChunkedDocs) {
      try {
        const { data } = await docApi.chunkBatch(kbId, [doc.id], doc.selected_method, chunkParams.value)
        results.push(...(data.results || []))
      } catch (error) {
        results.push({
          document_id: doc.id,
          success: false,
          error_message: error.response?.data?.detail || error.message,
        })
      }
    }

    showParamsDialog.value = false
    const successDocs = results.filter((item) => item.success).map((item) => item.document_id)

    if (successDocs.length > 0) {
      startProgressPolling(successDocs)
    }

    const successCount = results.filter((item) => item.success).length
    const failCount = results.length - successCount

    if (failCount === 0) {
      ElMessage.success(`已启动 ${successCount} 个文档的分块任务`)
    } else {
      ElMessage.warning(`已启动 ${successCount} 个文档的分块任务，${failCount} 个失败`)
      setTimeout(() => loadDocuments(), 1000)
    }
  } catch (error) {
    ElMessage.error('批量分块失败')
    loadDocuments()
  } finally {
    chunking.value = false
  }
}

async function viewChunks(doc) {
  try {
    const { data } = await docApi.chunks(kbId, doc.id, { page: 1, page_size: 100 })
    chunks.value = data.items || []
    showChunksDialog.value = true
  } catch (error) {
    ElMessage.error('加载分块结果失败')
  }
}

async function deleteDoc(doc) {
  try {
    await ElMessageBox.confirm('确定要删除这个文档吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })

    await docApi.delete(kbId, doc.id)
    ElMessage.success('删除成功')
    loadDocuments()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(`删除失败: ${error.response?.data?.detail || error.message}`)
    }
  }
}

async function batchDelete() {
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${selectedDocs.value.length} 个文档吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })

    let successCount = 0
    let failCount = 0

    for (const doc of selectedDocs.value) {
      try {
        await docApi.delete(kbId, doc.id)
        successCount += 1
      } catch {
        failCount += 1
      }
    }

    if (failCount === 0) {
      ElMessage.success(`成功删除 ${successCount} 个文档`)
    } else {
      ElMessage.warning(`成功删除 ${successCount} 个文档，失败 ${failCount} 个`)
    }

    loadDocuments()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('批量删除失败')
    }
  }
}

function formatTime(value) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

function backToList() {
  router.push('/knowledge')
}

function formatSize(size) {
  if (!size) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)} KB`
  return `${(size / 1024 / 1024).toFixed(2)} MB`
}

function getStatusType(status) {
  return {
    not_chunked: 'info',
    chunked: 'success',
    chunking: 'warning',
  }[status] || 'info'
}

function getStatusText(status) {
  return {
    not_chunked: '未分块',
    chunked: '已分块',
    chunking: '分块中',
  }[status] || status
}

function getMethodText(method) {
  if (!method) return '-'
  const found = chunkMethods.find((item) => item.value === method)
  return found ? found.name : method
}

function getFormatType(format) {
  return {
    pdf: 'danger',
    txt: 'info',
    md: 'success',
    csv: 'warning',
    doc: 'primary',
    docx: 'primary',
    xls: 'warning',
    xlsx: 'warning',
  }[format?.toLowerCase()] || 'info'
}

function safeParseArray(value) {
  try {
    const parsed = JSON.parse(value)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function safeParseObject(value) {
  try {
    return JSON.parse(value) || {}
  } catch {
    return {}
  }
}
</script>

<style scoped>
.doc-management {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.header-card {
  margin-bottom: 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.title-section {
  display: flex;
  align-items: center;
  gap: 15px;
}

.title-section h2 {
  margin: 0;
  font-size: 20px;
  color: #303133;
}

.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.chunk-content {
  max-height: 100px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 13px;
  line-height: 1.5;
}

.method-info-container {
  max-height: 600px;
  overflow-y: auto;
  padding: 10px;
}

.method-info-card {
  margin-bottom: 20px;
}

.method-info-card:last-child {
  margin-bottom: 0;
}

.method-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.method-name {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.method-info-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-item {
  display: flex;
  line-height: 1.6;
}

.info-label {
  font-weight: 600;
  color: #606266;
  min-width: 90px;
  flex-shrink: 0;
}

.info-text {
  color: #606266;
  flex: 1;
}

.scenario-text {
  color: #409eff;
  font-weight: 500;
}

.pros-item .info-text {
  color: #67c23a;
}

.cons-item .info-text {
  color: #e6a23c;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

.questions-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.question-item {
  font-size: 12px;
  line-height: 1.4;
  color: #606266;
}

.doc-name-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.doc-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.format-tag {
  flex-shrink: 0;
  font-weight: 600;
}

.chunking-status {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.progress-text {
  font-size: 12px;
  color: #606266;
}

@media (max-width: 960px) {
  .header-content {
    flex-direction: column;
    align-items: stretch;
  }

  .actions {
    justify-content: flex-start;
  }
}
</style>
