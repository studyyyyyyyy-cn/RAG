<template>
  <div class="vs-page">
    <div class="vs-header">
      <h2>向量库状态</h2>
      <el-tag :type="mode === 'Milvus' ? 'success' : 'warning'">{{ mode === 'Milvus' ? 'Milvus' : '内存模式' }}</el-tag>
      <el-button @click="load" :loading="loading" style="margin-left:12px"><el-icon><Refresh /></el-icon>刷新</el-button>
    </div>

    <!-- Progress overlay -->
    <div v-if="reloading" class="progress-bar">
      <el-alert :title="progressTitle" :description="progressDesc" type="info" show-icon :closable="false" />
      <el-progress :percentage="progressPercent" :stroke-width="16" :text-inside="true" style="margin-top:8px" />
    </div>

    <div v-loading="loading" class="vs-main">
      <el-empty v-if="!kbs.length" description="暂无知识库" />
      <el-table v-else :data="kbs" stripe border>
        <el-table-column prop="kb_name" label="知识库" min-width="120" />
        <el-table-column prop="mode" label="模式" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.mode==='Milvus'?'success':'warning'" size="small">{{ row.mode }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="doc_count" label="文档" width="60" align="center" />
        <el-table-column prop="chunk_vectors" label="Chunk" width="70" align="center">
          <template #default="{ row }">
            <span :style="{color: row.chunk_vectors>0?'#67c23a':'#f56c6c', fontWeight:'bold'}">{{ row.chunk_vectors }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="graph_vectors" label="图谱" width="70" align="center">
          <template #default="{ row }">
            <span :style="{color: row.graph_vectors>0?'#67c23a':'#f56c6c', fontWeight:'bold'}">{{ row.graph_vectors }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="neo4j_entities" label="节点" width="60" align="center" />
        <el-table-column prop="neo4j_relations" label="边" width="60" align="center" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.chunk_vectors===0" type="danger" size="small">需分块</el-tag>
            <el-tag v-else-if="row.graph_vectors===0" type="warning" size="small">需图谱</el-tag>
            <el-tag v-else type="success" size="small">正常</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary" size="small" :loading="reloading && reloadKbId===row.kb_id"
              :disabled="reloading" @click="startReload(row.kb_id)"
            >
              {{ reloading && reloadKbId===row.kb_id ? '处理中' : '重载' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

const kbs = ref([])
const loading = ref(false)
const mode = ref('')
const reloading = ref(false)
const reloadKbId = ref('')
const progressTitle = ref('')
const progressDesc = ref('')
const progressPercent = ref(0)

async function load() {
  loading.value = true
  try {
    const res = await api.get('/vector-status')
    kbs.value = res.data.knowledge_bases || []
    mode.value = res.data.mode || ''
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

function startReload(kbId) {
  reloading.value = true
  reloadKbId.value = kbId
  progressPercent.value = 0
  progressTitle.value = '连接中...'
  progressDesc.value = ''

  const url = `/api/v1/kb/${kbId}/reload-vectors`

  fetch(url, { headers: { Accept: 'text/event-stream' } }).then(response => {
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    function read() {
      reader.read().then(({ done, value }) => {
        if (done) {
          reloading.value = false
          reloadKbId.value = ''
          load()
          ElMessage.success('重载完成')
          return
        }
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            const eventType = line.slice(7).trim()
            // Find the data line
            const dataIdx = lines.indexOf(line) + 1
            if (dataIdx < lines.length && lines[dataIdx].startsWith('data: ')) {
              try {
                const data = JSON.parse(lines[dataIdx].slice(6))
                if (eventType === 'progress') {
                  progressTitle.value = data.message || ''
                  progressDesc.value = data.current || ''
                  if (data.overall_done && data.overall_total) {
                    progressPercent.value = Math.round((data.overall_done / data.overall_total) * 100)
                  } else if (data.total_chunks && data.chunk_index) {
                    progressPercent.value = Math.round((data.chunk_index / data.total_chunks) * 100)
                  }
                } else if (eventType === 'done') {
                  progressPercent.value = 100
                  progressTitle.value = '完成!'
                  progressDesc.value = data.message
                } else if (eventType === 'error') {
                  progressTitle.value = '错误: ' + data.message
                  reloading.value = false
                  reloadKbId.value = ''
                  ElMessage.error(data.message)
                }
              } catch (e) {}
            }
          }
        }
        if (reloading.value) read()
      })
    }
    read()
  }).catch(e => {
    reloading.value = false
    reloadKbId.value = ''
    ElMessage.error('连接失败: ' + e.message)
  })
}

onMounted(load)
</script>

<style scoped>
.vs-page { padding: 16px 24px; }
.vs-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.vs-header h2 { margin: 0; font-size: 20px; }
.progress-bar { margin-bottom: 12px; }
.vs-main { background: #fff; border-radius: 12px; padding: 16px; border: 1px solid #e4e7ed; }
</style>
