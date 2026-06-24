<template>
  <div class="api-test">
    <div class="page-header">
      <h2>API 接口测试</h2>
      <p class="subtitle">测试 REST API 接口：知识库管理、问答（支持智能体自动路由）</p>
    </div>

    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="知识库列表" name="knowledge">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>GET /api/v1/kb - 列出所有知识库</span>
              <el-button type="primary" size="small" @click="loadKnowledgeBases" :loading="loadingKb">
                刷新
              </el-button>
            </div>
          </template>
          <el-table :data="knowledgeBases" stripe border v-if="knowledgeBases.length > 0">
            <el-table-column prop="id" label="ID" width="280" />
            <el-table-column prop="name" label="名称" width="150" />
            <el-table-column prop="description" label="描述" />
            <el-table-column prop="doc_count" label="文档数" width="80" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'ready' ? 'success' : 'warning'">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无知识库" />
        </el-card>

        <el-card class="result-card">
          <template #header>
            <span>响应结果 (JSON)</span>
          </template>
          <pre class="json-result">{{ formatJson(kbListResult) }}</pre>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="问答接口" name="chat">
        <el-card>
          <el-form :model="chatForm" label-width="100px">
            <el-form-item label="知识库">
              <el-select v-model="chatForm.kb_id" placeholder="选择知识库" style="width: 100%">
                <el-option
                  v-for="kb in knowledgeBases"
                  :key="kb.id"
                  :label="kb.name"
                  :value="kb.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="问题">
              <el-input
                v-model="chatForm.query"
                type="textarea"
                rows="4"
                placeholder="请输入您的问题"
              />
            </el-form-item>
            <el-form-item label="流式输出">
              <el-switch v-model="chatForm.stream" />
              <span class="form-tip">启用后实时显示生成内容</span>
            </el-form-item>
            <el-form-item label="智能体路由">
              <el-switch v-model="chatForm.enable_agent" />
              <span class="form-tip">启用后自动判断是否使用图表/报表智能体</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="submitChat" :loading="loadingChat">
                {{ chatForm.stream ? '发送 (流式)' : '发送 (非流式)' }}
              </el-button>
              <el-button @click="clearChat">清空</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card v-if="chatResult" class="result-card">
          <template #header>
            <div class="card-header">
              <span>回答结果</span>
              <el-tag :type="getTypeTagType(chatResult.type)" size="small">
                {{ chatResult.type || 'text' }}
              </el-tag>
            </div>
          </template>
          <div class="chat-answer">
            <div v-if="chatResult.agent_type && chatResult.agent_type !== 'text'" class="agent-info-box">
              <el-icon><InfoFilled /></el-icon>
              <span>智能体类型: <strong>{{ chatResult.agent_type }}</strong></span>
            </div>
            <div class="answer-content">{{ chatResult.answer }}</div>
            <div v-if="chatResult.type === 'chart' && chatResult.chart_spec" class="chart-box">
              <h4>图表</h4>
              <ChartRenderer :option="chatResult.chart_spec" />
            </div>
            <div v-if="(chatResult.type === 'report' || chatResult.type === 'webpage') && chatResult.html_content" class="html-box">
              <h4>HTML 内容</h4>
              <div class="html-preview" v-html="chatResult.html_content"></div>
            </div>
            <div v-if="chatResult.type === 'composite' && chatResult.data_table" class="data-table-box">
              <h4>数据表格</h4>
              <el-table :data="tableRows" size="small" stripe border>
                <el-table-column
                  v-for="h in chatResult.data_table.headers"
                  :key="h"
                  :prop="h"
                  :label="h"
                />
              </el-table>
            </div>
            <div v-if="chatResult.insights?.length" class="insights-box">
              <h4>数据洞察</h4>
              <ul>
                <li v-for="(ins, idx) in chatResult.insights" :key="idx">{{ ins }}</li>
              </ul>
            </div>
            <div v-if="chatResult.references?.length" class="references">
              <h4>参考资料</h4>
              <el-tag
                v-for="(ref, idx) in chatResult.references"
                :key="idx"
                class="ref-tag"
              >
                {{ ref.source }}<span v-if="ref.page"> - 页{{ ref.page }}</span>
              </el-tag>
            </div>
            <div class="metadata">
              <span>置信度: {{ (chatResult.confidence * 100).toFixed(1) }}%</span>
              <span v-if="chatResult.model_used">模型: {{ chatResult.model_used }}</span>
            </div>
          </div>
        </el-card>

        <el-card v-if="streamOutput" class="result-card">
          <template #header>
            <span>流式输出</span>
          </template>
          <div class="stream-output">{{ streamOutput }}</div>
        </el-card>

        <el-card v-if="rawResponse" class="result-card">
          <template #header>
            <div class="card-header">
              <span>原始响应 (JSON)</span>
              <el-button type="primary" size="small" @click="copyResponse">
                复制
              </el-button>
            </div>
          </template>
          <pre class="json-result raw-json">{{ formatJson(rawResponse) }}</pre>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="cURL 示例" name="curl">
        <el-card>
          <template #header>
            <span>接口调用示例</span>
          </template>
          <div class="curl-examples">
            <h4>知识库列表</h4>
            <div class="curl-code">
              <pre>curl http://localhost:8000/api/v1/kb</pre>
            </div>

            <h4>问答接口 (非流式)</h4>
            <div class="curl-code">
              <pre>curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "生成销售数据图表",
    "kb_id": "kb_001",
    "stream": false,
    "enable_agent": true
  }'</pre>
            </div>

            <h4>问答接口 (流式)</h4>
            <div class="curl-code">
              <pre>curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "什么是RAG?",
    "kb_id": "kb_001",
    "stream": true,
    "enable_agent": true
  }'</pre>
            </div>
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'
import { kbApi } from '@/api'
import ChartRenderer from '@/components/ChartRenderer.vue'

const activeTab = ref('knowledge')
const knowledgeBases = ref([])
const kbListResult = ref(null)
const loadingKb = ref(false)
const loadingChat = ref(false)

const chatForm = ref({
  kb_id: '',
  query: '',
  stream: true,
  enable_agent: true
})

const chatResult = ref(null)
const streamOutput = ref('')
const rawResponse = ref(null)

const tableRows = computed(() => {
  const dt = chatResult.value?.data_table
  if (!dt?.headers || !dt?.rows) return []
  return dt.rows.map((row) => {
    const obj = {}
    dt.headers.forEach((h, i) => { obj[h] = row[i] ?? '' })
    return obj
  })
})

const getTypeTagType = (type) => {
  const typeMap = {
    'text': '',
    'chart': 'success',
    'report': 'warning',
    'webpage': 'info',
    'composite': 'danger'
  }
  return typeMap[type] || ''
}

const formatJson = (data) => {
  if (data === null || data === undefined) return ''
  try {
    return JSON.stringify(data, null, 2)
  } catch (e) {
    return String(data)
  }
}

const copyResponse = async () => {
  try {
    await navigator.clipboard.writeText(formatJson(rawResponse.value))
    ElMessage.success('已复制到剪贴板')
  } catch (e) {
    ElMessage.error('复制失败')
  }
}

const loadKnowledgeBases = async () => {
  loadingKb.value = true
  try {
    const res = await kbApi.list()
    kbListResult.value = res.data
    knowledgeBases.value = res.data.items || []
    if (knowledgeBases.value.length > 0 && !chatForm.value.kb_id) {
      chatForm.value.kb_id = knowledgeBases.value[0].id
    }
  } catch (e) {
    console.error('加载知识库失败:', e)
    kbListResult.value = { error: e.message }
    ElMessage.error('加载知识库失败: ' + e.message)
  } finally {
    loadingKb.value = false
  }
}

const parseSSE = (text) => {
  const lines = text.split('\n')
  const events = []
  let currentEvent = {}
  
  for (const line of lines) {
    if (line.startsWith('event:')) {
      currentEvent.event = line.substring(6).trim()
    } else if (line.startsWith('data:')) {
      const dataStr = line.substring(5).trim()
      try {
        currentEvent.data = JSON.parse(dataStr)
      } catch (e) {
        currentEvent.data = dataStr
      }
    } else if (line === '' && (currentEvent.event || currentEvent.data)) {
      events.push(currentEvent)
      currentEvent = {}
    }
  }
  
  if (currentEvent.event || currentEvent.data) {
    events.push(currentEvent)
  }
  
  return events
}

const submitChat = async () => {
  if (!chatForm.value.kb_id || !chatForm.value.query) {
    ElMessage.warning('请选择知识库并输入问题')
    return
  }

  loadingChat.value = true
  chatResult.value = null
  streamOutput.value = ''
  rawResponse.value = null

  try {
    if (chatForm.value.stream) {
      const response = await fetch('/api/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(chatForm.value)
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      const allEvents = []

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const events = parseSSE(buffer)
        buffer = ''

        for (const event of events) {
          allEvents.push(event)
          if (event.event === 'text_chunk' && event.data?.text) {
            streamOutput.value += event.data.text
          } else if (event.event === 'metadata') {
            chatResult.value = {
              answer: '',
              references: event.data.citations || [],
              confidence: event.data.confidence || 0,
              model_used: event.data.model_used,
              agent_type: event.data.agent_type || 'text',
              type: event.data.agent_type || 'text'
            }
          } else if (event.event === 'done') {
            if (chatResult.value) {
              chatResult.value.answer = streamOutput.value
              chatResult.value.type = event.data?.type || chatResult.value.type
            }
          } else if (event.event === 'complete') {
            console.log('Stream complete:', event.data)
          } else if (event.event === 'error') {
            ElMessage.error('流式响应错误: ' + (event.data?.detail || 'Unknown error'))
          }
        }
      }

      if (chatResult.value) {
        chatResult.value.answer = streamOutput.value
      } else {
        chatResult.value = {
          answer: streamOutput.value,
          type: 'text',
          confidence: 0,
          references: []
        }
      }

      rawResponse.value = {
        stream: true,
        events: allEvents,
        finalResult: chatResult.value
      }
    } else {
      const res = await fetch('/api/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(chatForm.value)
      })
      const data = await res.json()
      rawResponse.value = data
      
      if (data.answer?.content) {
        const content = data.answer.content
        chatResult.value = {
          answer: content.text,
          references: content.citations,
          confidence: data.answer.confidence,
          model_used: data.answer.metadata?.model_used,
          agent_type: data.answer.metadata?.agent_type,
          type: data.answer.type,
          chart_spec: content.chart_spec,
          html_content: content.html_content,
          data_table: content.data_table,
          insights: content.insights
        }
      }
    }
  } catch (e) {
    ElMessage.error('请求失败: ' + e.message)
    console.error('Chat error:', e)
    rawResponse.value = { error: e.message }
  } finally {
    loadingChat.value = false
  }
}

const clearChat = () => {
  chatResult.value = null
  streamOutput.value = ''
  rawResponse.value = null
}

onMounted(() => {
  loadKnowledgeBases()
})
</script>

<style scoped>
.api-test {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0 0 8px 0;
}

.subtitle {
  color: #909399;
  margin: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-card {
  margin-top: 20px;
}

.form-tip {
  margin-left: 12px;
  color: #909399;
  font-size: 13px;
}

.json-result {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 8px;
  font-size: 13px;
  max-height: 500px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

.raw-json {
  background: #1e1e1e;
  color: #d4d4d4;
}

.chat-answer {
  line-height: 1.8;
}

.agent-info-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #e6f7ff;
  border-radius: 8px;
  margin-bottom: 16px;
  color: #1890ff;
}

.answer-content {
  margin-bottom: 16px;
  white-space: pre-wrap;
  padding: 16px;
  background: #fafafa;
  border-radius: 8px;
}

.chart-box {
  margin: 16px 0;
  padding: 16px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
}

.chart-box h4 {
  margin: 0 0 12px 0;
  color: #606266;
}

.html-box {
  margin: 16px 0;
  padding: 16px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
}

.html-box h4 {
  margin: 0 0 12px 0;
  color: #606266;
}

.html-preview {
  max-height: 400px;
  overflow: auto;
  padding: 12px;
  background: #fafafa;
  border-radius: 4px;
}

.data-table-box {
  margin: 16px 0;
  padding: 16px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
}

.data-table-box h4 {
  margin: 0 0 12px 0;
  color: #606266;
}

.insights-box {
  margin: 16px 0;
  padding: 16px;
  background: #f6ffed;
  border-radius: 8px;
}

.insights-box h4 {
  margin: 0 0 12px 0;
  color: #52c41a;
}

.insights-box ul {
  margin: 0;
  padding-left: 20px;
}

.insights-box li {
  margin-bottom: 8px;
}

.references {
  border-top: 1px solid #eee;
  padding-top: 16px;
  margin-top: 16px;
}

.references h4 {
  margin: 0 0 12px 0;
}

.ref-tag {
  margin-right: 8px;
  margin-bottom: 8px;
}

.metadata {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #eee;
  font-size: 13px;
  color: #909399;
}

.metadata span {
  margin-right: 16px;
}

.stream-output {
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.8;
  background: #f5f7fa;
  padding: 16px;
  border-radius: 8px;
}

.curl-examples h4 {
  margin: 20px 0 10px 0;
  color: #409eff;
}

.curl-examples h4:first-child {
  margin-top: 0;
}

.curl-code {
  background: #1d1e2c;
  color: #a3a6b4;
  padding: 12px 16px;
  border-radius: 4px;
  overflow-x: auto;
}

.curl-code pre {
  margin: 0;
  font-family: 'Consolas', monospace;
  font-size: 13px;
}
</style>
