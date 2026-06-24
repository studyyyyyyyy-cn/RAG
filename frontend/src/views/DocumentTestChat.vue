<template>
  <div class="test-chat-container">
    <div class="page-header">
      <div class="header-left">
        <el-button text @click="$router.back()">
          <el-icon><ArrowLeft /></el-icon> 返回
        </el-button>
        <h2>{{ kbName }} - 测试问答</h2>
      </div>
    </div>

    <div class="content-wrapper">
      <!-- 左侧：问答区域 -->
      <div class="chat-panel">
        <div class="query-input">
          <el-input
            v-model="testQuery"
            placeholder="输入测试问题..."
            @keyup.enter="submitQuery"
            :disabled="loading"
          >
            <template #append>
              <el-button
                type="primary"
                @click="submitQuery"
                :loading="loading"
                :disabled="!testQuery.trim()"
              >
                测试
              </el-button>
            </template>
          </el-input>
        </div>

        <div class="answer-section" v-if="answer">
          <div class="section-title">回答</div>
          <div class="answer-content">{{ answer }}</div>

          <div class="confidence-badge">
            <el-tag :type="confidenceType">
              置信度: {{ (confidence * 100).toFixed(1) }}% ({{ confidenceLabel }})
            </el-tag>
          </div>

          <div class="sources-section" v-if="sources.length">
            <div class="section-title">引用来源</div>
            <el-card
              v-for="(source, index) in sources"
              :key="index"
              class="source-card"
              shadow="hover"
            >
              <div class="source-header">
                <el-tag size="small" type="info">相关度: {{ (source.relevance * 100).toFixed(1) }}%</el-tag>
                <span v-if="source.page_number" class="page-info">页码: {{ source.page_number }}</span>
                <span v-if="source.section_title" class="section-info">{{ source.section_title }}</span>
              </div>
              <div class="source-content">{{ source.content }}</div>
            </el-card>
          </div>
        </div>

        <el-empty v-else description="输入问题开始测试" />
      </div>

      <!-- 右侧：调试信息面板 -->
      <div class="debug-panel" v-if="debugData">
        <el-tabs v-model="activeTab">
          <!-- Tab 1: 检索过程 -->
          <el-tab-pane label="检索过程" name="retrieval">
            <el-timeline>
              <el-timeline-item
                v-if="debugData.rewritten_query"
                title="查询改写"
                timestamp="Step 1"
              >
                <div class="timeline-content">
                  <div><strong>原始查询:</strong> {{ debugData.query }}</div>
                  <div><strong>改写后:</strong> {{ debugData.rewritten_query }}</div>
                </div>
              </el-timeline-item>

              <el-timeline-item
                title="向量检索"
                :timestamp="`Step 2 (${debugData.metrics?.retrieval_time_ms || 0}ms)`"
              >
                <div class="timeline-content">
                  <div class="stats-info">
                    检索到 {{ debugData.retrieval_results?.length || 0 }} 个候选分块
                  </div>
                  <el-collapse accordion>
                    <el-collapse-item
                      v-for="(chunk, idx) in debugData.retrieval_results"
                      :key="idx"
                      :title="`分块 #${idx + 1}`"
                    >
                      <div class="chunk-scores">
                        <el-tag size="small">Dense: {{ chunk.dense_score?.toFixed(3) }}</el-tag>
                        <el-tag size="small" type="success" v-if="chunk.sparse_score">
                          Sparse: {{ chunk.sparse_score.toFixed(3) }}
                        </el-tag>
                        <el-tag size="small" type="warning">
                          Hybrid: {{ chunk.hybrid_score?.toFixed(3) }}
                        </el-tag>
                      </div>
                      <div class="chunk-meta">
                        <span v-if="chunk.document">文档: {{ chunk.document }}</span>
                        <span v-if="chunk.page">页码: {{ chunk.page }}</span>
                        <span v-if="chunk.section">章节: {{ chunk.section }}</span>
                      </div>
                      <div class="chunk-content">{{ chunk.content }}</div>
                    </el-collapse-item>
                  </el-collapse>
                </div>
              </el-timeline-item>

              <el-timeline-item
                v-if="debugData.reranked_results"
                title="重排序"
                :timestamp="`Step 3 (${debugData.metrics?.rerank_time_ms || 0}ms)`"
              >
                <div class="timeline-content">
                  <div class="stats-info">
                    重排序后选中 {{ debugData.selected_chunks?.length || 0 }} 个分块
                  </div>
                  <el-table :data="debugData.reranked_results" size="small">
                    <el-table-column prop="content" label="内容" width="300">
                      <template #default="{ row }">
                        {{ row.content.substring(0, 50) }}...
                      </template>
                    </el-table-column>
                    <el-table-column prop="rerank_score" label="重排序分数" width="120">
                      <template #default="{ row }">
                        {{ row.rerank_score?.toFixed(3) }}
                      </template>
                    </el-table-column>
                  </el-table>
                </div>
              </el-timeline-item>

              <el-timeline-item
                title="上下文构建"
                timestamp="Step 4"
              >
                <div class="timeline-content">
                  <el-descriptions :column="2" size="small">
                    <el-descriptions-item label="选中分块数">
                      {{ debugData.selected_chunks?.length || 0 }}
                    </el-descriptions-item>
                    <el-descriptions-item label="上下文长度">
                      {{ debugData.context_length || 0 }} tokens
                    </el-descriptions-item>
                  </el-descriptions>
                </div>
              </el-timeline-item>
            </el-timeline>
          </el-tab-pane>

          <!-- Tab 2: Prompt 查看 -->
          <el-tab-pane label="Prompt" name="prompt">
            <el-input
              type="textarea"
              :rows="20"
              v-model="debugData.prompt_template"
              readonly
              class="prompt-textarea"
            />
          </el-tab-pane>

          <!-- Tab 3: 性能指标 -->
          <el-tab-pane label="性能" name="metrics">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="检索耗时">
                {{ debugData.metrics?.retrieval_time_ms || 0 }} ms
              </el-descriptions-item>
              <el-descriptions-item label="重排序耗时">
                {{ debugData.metrics?.rerank_time_ms || 0 }} ms
              </el-descriptions-item>
              <el-descriptions-item label="生成耗时">
                {{ debugData.metrics?.generation_time_ms || 0 }} ms
              </el-descriptions-item>
              <el-descriptions-item label="总耗时">
                {{ debugData.metrics?.total_time_ms || 0 }} ms
              </el-descriptions-item>
              <el-descriptions-item label="输入 Tokens">
                {{ debugData.metrics?.input_tokens || 0 }}
              </el-descriptions-item>
              <el-descriptions-item label="输出 Tokens">
                {{ debugData.metrics?.output_tokens || 0 }}
              </el-descriptions-item>
              <el-descriptions-item label="总 Tokens">
                {{ debugData.metrics?.total_tokens || 0 }}
              </el-descriptions-item>
            </el-descriptions>
          </el-tab-pane>

          <!-- Tab 4: 原始数据 -->
          <el-tab-pane label="原始 JSON" name="raw">
            <pre class="json-display">{{ JSON.stringify(debugData, null, 2) }}</pre>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'

const route = useRoute()
const kbId = route.params.id
const kbName = ref('')

const testQuery = ref('')
const loading = ref(false)
const answer = ref('')
const confidence = ref(0)
const confidenceLabel = ref('')
const sources = ref([])
const debugData = ref(null)
const activeTab = ref('retrieval')

const confidenceType = computed(() => {
  if (confidence.value >= 0.8) return 'success'
  if (confidence.value >= 0.6) return 'warning'
  return 'danger'
})

onMounted(async () => {
  const { kbApi } = await import('@/api')
  try {
    const { data } = await kbApi.get(kbId)
    kbName.value = data.name
  } catch (e) {
    ElMessage.error('加载知识库信息失败')
  }
})

async function submitQuery() {
  if (!testQuery.value.trim()) return

  loading.value = true
  answer.value = ''
  sources.value = []
  debugData.value = null

  try {
    const { chatApi } = await import('@/api')
    const { data } = await chatApi.testChat(kbId, {
      query: testQuery.value,
      debug: true
    })

    // 设置回答和来源
    answer.value = data.answer
    confidence.value = data.confidence || 0
    confidenceLabel.value = data.confidence_label || ''
    sources.value = data.sources || []

    // 设置调试数据
    debugData.value = data

    ElMessage.success('测试完成')
  } catch (e) {
    ElMessage.error(`测试失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.test-chat-container {
  padding: 20px;
  height: calc(100vh - 40px);
  display: flex;
  flex-direction: column;
}

.page-header {
  margin-bottom: 20px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-left h2 {
  font-size: 20px;
  color: #303133;
}

.content-wrapper {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  overflow: hidden;
}

.chat-panel,
.debug-panel {
  background: white;
  border-radius: 8px;
  padding: 20px;
  overflow-y: auto;
}

.query-input {
  margin-bottom: 20px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
}

.answer-section {
  margin-top: 20px;
}

.answer-content {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 8px;
  line-height: 1.8;
  color: #303133;
  margin-bottom: 16px;
  white-space: pre-wrap;
}

.confidence-badge {
  margin-bottom: 20px;
}

.sources-section {
  margin-top: 20px;
}

.source-card {
  margin-bottom: 12px;
}

.source-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 13px;
  color: #606266;
}

.source-content {
  color: #303133;
  line-height: 1.6;
  font-size: 14px;
}

.timeline-content {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
}

.stats-info {
  margin-bottom: 12px;
  color: #606266;
  font-size: 14px;
}

.chunk-scores {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.chunk-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
  font-size: 13px;
  color: #909399;
}

.chunk-content {
  padding: 12px;
  background: white;
  border-radius: 4px;
  line-height: 1.6;
  color: #303133;
  font-size: 14px;
}

.prompt-textarea {
  font-family: 'Courier New', monospace;
  font-size: 13px;
}

.json-display {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 4px;
  overflow-x: auto;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #303133;
}
</style>
