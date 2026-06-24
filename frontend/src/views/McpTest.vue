<template>
  <div class="mcp-test">
    <div class="page-header">
      <h2>MCP 工具测试</h2>
      <p class="subtitle">测试 MCP 协议接口，验证 RAG 能力</p>
    </div>

    <el-card class="status-card">
      <template #header>
        <div class="card-header">
          <span>MCP 服务连接信息</span>
          <el-tag :type="mcpConnected ? 'success' : 'danger'">
            {{ mcpConnected ? '已连接' : '未连接' }}
          </el-tag>
        </div>
      </template>

      <div class="connection-info">
        <div class="info-item">
          <span class="label">SSE 连接地址:</span>
          <code class="address">{{ mcpSseUrl }}</code>
          <el-button type="primary" size="small" style="margin-left: 8px" @click="copyUrl">复制</el-button>
          <el-button type="primary" size="small" :loading="testing" @click="testConnection()">
            {{ testing ? '测试中...' : '测试连接' }}
          </el-button>
        </div>
        <div class="info-item">
          <span class="label">传输方式:</span>
          <span>SSE (Server-Sent Events)</span>
        </div>
        <div class="info-item">
          <span class="label">MCP 版本:</span>
          <span>2024-11-05</span>
        </div>
        <div class="info-item">
          <span class="label">消息端点:</span>
          <code class="address">{{ mcpMessageUrl }}</code>
        </div>
        <div class="info-item">
          <span class="label">Claude Desktop 配置:</span>
          <pre class="config-code">{
  "mcpServers": {
    "ragapp": {
      "url": "{{ mcpSseUrl }}"
    }
  }
}</pre>
        </div>
        <div class="info-item">
          <span class="label">Cursor / VS Code 配置:</span>
          <pre class="config-code">{
  "mcp": {
    "servers": {
      "ragapp": {
        "url": "{{ mcpSseUrl }}"
      }
    }
  }
}</pre>
        </div>
        <div class="info-item prompt-item">
          <span class="label">提示词参考:</span>
          <div class="prompt-block">
            <pre class="config-code">{{ mcpPromptTemplate }}</pre>
            <el-button type="primary" size="small" @click="copyPrompt">复制提示词</el-button>
          </div>
        </div>
        <div v-if="connectionError" class="error-msg">{{ connectionError }}</div>
      </div>
    </el-card>

    <el-card class="tool-card">
      <template #header>
        <div class="card-header">
          <span>工具 1: list_knowledge_bases</span>
          <el-button type="primary" size="small" :loading="loadingKb" @click="callListKb">执行</el-button>
        </div>
      </template>
      <p class="tool-desc">列出所有可用的知识库</p>
      <div v-if="kbResult" class="result-area">
        <pre>{{ JSON.stringify(kbResult, null, 2) }}</pre>
      </div>
    </el-card>

    <el-card class="tool-card">
      <template #header>
        <div class="card-header">
          <span>工具 2: rag_chat (RAG问答)</span>
        </div>
      </template>
      <p class="tool-desc">检索相关文档并生成完整答案，支持智能体自动路由。</p>

      <el-form :model="chatForm" label-width="100px">
        <el-form-item label="知识库">
          <el-select v-model="chatForm.kb_id" placeholder="选择知识库" style="width: 100%">
            <el-option v-for="kb in knowledgeBases" :key="kb.id" :label="kb.name" :value="kb.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="问题">
          <el-input v-model="chatForm.query" type="textarea" rows="3" placeholder="输入问题" />
        </el-form-item>
        <el-form-item label="top_k">
          <el-input-number v-model="chatForm.top_k" :min="1" :max="20" />
        </el-form-item>
        <el-form-item label="智能体路由">
          <el-switch v-model="chatForm.enable_agent" active-text="启用" inactive-text="禁用" />
          <span class="form-tip">启用后系统会自动判断是否使用图表、报表等智能体</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loadingChat" @click="callRagChat">执行问答</el-button>
        </el-form-item>
      </el-form>

      <div v-if="chatResult" class="result-area">
        <div class="answer-box">
          <h4>答案:</h4>
          <p>{{ chatResult.answer }}</p>
        </div>

        <div v-if="chatResult.type === 'chart' && chatResult.chart_spec" class="chart-box">
          <h4>图表:</h4>
          <ChartRenderer :option="chatResult.chart_spec" />
        </div>

        <div v-if="(chatResult.type === 'report' || chatResult.type === 'webpage') && chatResult.html_content" class="html-box">
          <h4>HTML 内容:</h4>
          <div class="html-preview" v-html="chatResult.html_content"></div>
        </div>

        <div v-if="chatResult.type === 'composite' && chatResult.data_table" class="data-table-box">
          <h4>数据表格:</h4>
          <el-table :data="tableRows" size="small" stripe border>
            <el-table-column v-for="h in chatResult.data_table.headers" :key="h" :prop="h" :label="h" />
          </el-table>
        </div>

        <div v-if="chatResult.insights?.length" class="insights-box">
          <h4>数据洞察:</h4>
          <ul>
            <li v-for="(ins, idx) in chatResult.insights" :key="idx">{{ ins }}</li>
          </ul>
        </div>

        <div v-if="chatResult.references?.length" class="references-box">
          <h4>参考资料:</h4>
          <ul>
            <li v-for="(ref, idx) in chatResult.references" :key="idx">
              {{ ref.source }}<span v-if="ref.page"> (页 {{ ref.page }})</span>
            </li>
          </ul>
        </div>

        <div class="metadata-box">
          <h4>元数据:</h4>
          <p>类型: {{ chatResult.type || 'text' }}</p>
          <p>置信度: {{ chatResult.confidence }}</p>
          <p>模型: {{ chatResult.model_used }}</p>
          <p>智能体类型: {{ chatResult.agent_type || 'text' }}</p>
        </div>

        <pre class="raw-json">{{ JSON.stringify(chatResult, null, 2) }}</pre>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { kbApi } from '@/api'
import ChartRenderer from '@/components/ChartRenderer.vue'

const mcpConnected = ref(false)
const testing = ref(false)
const connectionError = ref('')
const knowledgeBases = ref([])
const loadingKb = ref(false)
const loadingChat = ref(false)

const kbResult = ref('')
const chatResult = ref('')

const chatForm = ref({
  kb_id: '',
  query: '',
  top_k: 5,
  enable_agent: true,
})

const baseUrl = window.location.origin
const mcpSseUrl = `${baseUrl}/mcp/sse`
const mcpMessageUrl = `${baseUrl}/mcp/message`
const mcpPromptTemplate = `请把下面这个 MCP 服务接入到你的工具调用环境中，并优先把它作为知识库问答工具使用。

MCP 服务名称：ragapp
SSE 地址：${mcpSseUrl}
消息地址：${mcpMessageUrl}
协议：MCP over SSE

接入目标：
1. 连接这个 MCP 服务
2. 识别并加载它提供的工具
3. 在需要知识库检索、RAG问答、列出知识库等场景时优先调用这些工具
4. 回答问题时，优先基于知识库检索结果生成答案
5. 如果工具返回来源、页码或引用信息，请在最终回答中保留

推荐使用方式：
- 当用户询问企业知识、项目文档、内部资料时，先调用 ragapp 相关工具
- 当用户要求列出知识库时，调用 list_knowledge_bases
- 当用户要求基于知识库回答问题时，调用 rag_chat

如果你的环境支持 MCP 配置，请使用上面的 SSE 地址完成连接。`

const tableRows = computed(() => {
  const dt = chatResult.value?.data_table
  if (!dt?.headers || !dt?.rows) return []
  return dt.rows.map((row) => {
    const obj = {}
    dt.headers.forEach((h, i) => {
      obj[h] = row[i] ?? ''
    })
    return obj
  })
})

const loadKnowledgeBases = async () => {
  try {
    const res = await kbApi.list()
    knowledgeBases.value = res.data.items || []
    if (knowledgeBases.value.length > 0) {
      chatForm.value.kb_id = knowledgeBases.value[0].id
    }
  } catch (e) {
    console.error('加载知识库失败', e)
  }
}

const copyUrl = async () => {
  try {
    await navigator.clipboard.writeText(mcpSseUrl)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

const copyPrompt = async () => {
  try {
    await navigator.clipboard.writeText(mcpPromptTemplate)
    ElMessage.success('已复制提示词')
  } catch {
    ElMessage.error('复制失败')
  }
}

const testConnection = async (silent = false) => {
  testing.value = true
  connectionError.value = ''
  try {
    const res = await fetch('/mcp/sse')
    if (res.ok) {
      mcpConnected.value = true
      if (!silent) {
        ElMessage.success('MCP 服务连接正常 (SSE)')
      }
    } else {
      mcpConnected.value = false
      connectionError.value = `连接失败: HTTP ${res.status}`
    }
  } catch (e) {
    connectionError.value = `连接失败: ${e.message}`
    mcpConnected.value = false
  } finally {
    testing.value = false
  }
}

const callListKb = async () => {
  loadingKb.value = true
  kbResult.value = ''
  try {
    const res = await kbApi.list()
    kbResult.value = res.data
  } catch (e) {
    kbResult.value = { error: e.message }
  } finally {
    loadingKb.value = false
  }
}

const callRagChat = async () => {
  if (!chatForm.value.kb_id || !chatForm.value.query) {
    ElMessage.warning('请选择知识库并输入问题')
    return
  }

  loadingChat.value = true
  chatResult.value = ''
  try {
    const res = await fetch('/api/v1/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...chatForm.value,
        stream: false,
      }),
    })
    const data = await res.json()
    if (data.answer?.content) {
      const content = data.answer.content
      chatResult.value = {
        answer: content.text,
        type: data.answer.type || 'text',
        references: content.citations,
        confidence: data.answer.confidence,
        model_used: data.answer.metadata?.model_used,
        agent_type: data.answer.metadata?.agent_type || 'text',
        chart_spec: content.chart_spec,
        html_content: content.html_content,
        data_table: content.data_table,
        insights: content.insights,
      }
    } else {
      chatResult.value = data
    }
  } catch (e) {
    chatResult.value = { error: e.message }
  } finally {
    loadingChat.value = false
  }
}

onMounted(() => {
  loadKnowledgeBases()
  testConnection(true)
})
</script>

<style scoped>
.mcp-test {
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

.status-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.connection-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.prompt-item {
  align-items: stretch;
}

.info-item .label {
  min-width: 140px;
  font-weight: 500;
  color: #606266;
}

.info-item code.address {
  background: #f5f7fa;
  padding: 4px 8px;
  border-radius: 4px;
  font-family: Consolas, monospace;
  color: #409eff;
}

.config-code {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-family: Consolas, monospace;
  font-size: 13px;
  color: #303133;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  flex: 1;
}

.prompt-block {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 10px;
}

.error-msg {
  color: #f56c6c;
}

.tool-card {
  margin-bottom: 20px;
}

.tool-desc {
  color: #909399;
  margin-bottom: 16px;
  font-size: 14px;
}

.form-tip {
  margin-left: 12px;
  color: #909399;
  font-size: 13px;
}

.result-area {
  margin-top: 16px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  max-height: 800px;
  overflow: auto;
}

.result-area pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 13px;
}

.answer-box {
  margin-bottom: 16px;
  padding: 16px;
  background: #e6f7ff;
  border-radius: 8px;
}

.answer-box h4 {
  margin: 0 0 12px 0;
  color: #1890ff;
}

.answer-box p {
  margin: 0;
  line-height: 1.8;
}

.chart-box,
.html-box,
.data-table-box {
  margin-bottom: 16px;
  padding: 16px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}

.chart-box h4,
.html-box h4,
.data-table-box h4 {
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

.insights-box {
  margin-bottom: 16px;
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
  color: #333;
  line-height: 1.6;
}

.references-box {
  margin-bottom: 16px;
  padding: 16px;
  background: #fff7e6;
  border-radius: 8px;
}

.references-box h4 {
  margin: 0 0 12px 0;
  color: #fa8c16;
}

.references-box ul {
  margin: 0;
  padding-left: 20px;
}

.references-box li {
  margin-bottom: 4px;
  color: #666;
}

.metadata-box {
  margin-bottom: 16px;
  padding: 12px 16px;
  background: #f0f2f5;
  border-radius: 8px;
  font-size: 13px;
}

.metadata-box h4 {
  margin: 0 0 8px 0;
  color: #606266;
  font-size: 14px;
}

.metadata-box p {
  margin: 4px 0;
  color: #909399;
}

.raw-json {
  margin-top: 16px;
  padding: 12px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 8px;
  font-size: 12px;
}
</style>
