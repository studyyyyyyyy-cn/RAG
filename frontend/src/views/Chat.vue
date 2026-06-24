<template>
  <div class="chat-shell">
    <div class="chat-container">
      <div class="chat-sidebar">
        <div class="sidebar-top">
          <div class="sidebar-title">智能问答</div>
          <div class="sidebar-subtitle">彩色知识对话台</div>
        </div>

        <el-select v-model="selectedKb" placeholder="选择知识库" class="kb-select" @change="onKbChange">
          <el-option v-for="kb in kbStore.knowledgeBases" :key="kb.id" :label="kb.name" :value="kb.id" />
        </el-select>

        <el-button class="new-chat-btn" text @click="newConversation">
          <el-icon><Plus /></el-icon> 新对话
        </el-button>

        <div class="history-list">
          <div
            v-for="conv in conversations"
            :key="conv.id"
            class="history-item"
            :class="{ active: chatStore.conversationId === conv.id }"
          >
            <div class="history-content" @click="loadConversation(conv.id)">
              {{ conv.title }}
            </div>
            <div class="history-actions">
              <el-icon class="action-icon edit-icon" @click.stop="editTitle(conv)">
                <Edit />
              </el-icon>
              <el-icon class="action-icon delete-icon" @click.stop="confirmDelete(conv.id)">
                <Delete />
              </el-icon>
            </div>
          </div>
          <el-empty v-if="conversations.length === 0" description="暂无历史对话" :image-size="60" />
        </div>
      </div>

      <div class="chat-main">
        <div class="main-hero">
          <div>
            <h2>{{ currentConversationTitle }}</h2>
          </div>
          <div class="hero-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>

        <div class="messages-area" ref="messagesArea">
          <el-empty v-if="chatStore.messages.length === 0" description="选择知识库并输入问题开始对话" />

          <div v-for="(msg, i) in chatStore.messages" :key="i" class="message-row" :class="msg.role">
            <ChatMessage
              :message="msg"
              :streaming="chatStore.streaming && i === chatStore.messages.length - 1"
              :waiting-seconds="msg.waiting ? waitingSeconds : 0"
              @save-shortcut="handleSaveShortcut(msg, i)"
            />
          </div>
        </div>

        <div class="input-area">
          <div class="input-box">
            <el-input
              v-model="inputText"
              type="textarea"
              :rows="2"
              placeholder="输入问题... (Enter 发送，Shift+Enter 换行)"
              :disabled="chatStore.streaming"
              @keydown.enter.exact.prevent="handleSend"
            />
            <el-button
              type="primary"
              :icon="Promotion"
              circle
              class="send-btn"
              :loading="chatStore.streaming"
              @click="handleSend"
            />
          </div>

          <div class="input-toolbar">
            <el-select
              v-model="selectedLlm"
              placeholder="LLM 模型"
              size="small"
              class="toolbar-select"
              clearable
              @change="onLlmChange"
            >
              <el-option v-for="c in llmConfigs" :key="c.id" :label="c.display_name" :value="c.id" />
            </el-select>

            <el-dropdown trigger="click" @command="handleAgentCommand">
              <el-button size="small" type="primary" plain class="agent-btn">
                <el-icon><MagicStick /></el-icon> 手动选择智能体
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="chart">生成图表</el-dropdown-item>
                  <el-dropdown-item command="report">生成报表</el-dropdown-item>
                  <el-dropdown-item command="data_table">数据分析</el-dropdown-item>
                  <el-dropdown-item command="webpage">网页展示</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Delete, Edit, MagicStick, Plus, Promotion } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { agentApi, chatApi, llmApi, shortcutApi } from '@/api'
import ChatMessage from '@/components/ChatMessage.vue'
import { useChatStore } from '@/stores/chat'
import { useKnowledgeStore } from '@/stores/knowledge'

const route = useRoute()
const kbStore = useKnowledgeStore()
const chatStore = useChatStore()

const selectedKb = ref(route.query.kb_id || localStorage.getItem('lastKbId') || '')
const selectedLlm = ref(null)
const inputText = ref('')
const conversations = ref([])
const llmConfigs = ref([])
const messagesArea = ref(null)
const agentLoading = ref(false)
const waitingSeconds = ref(0)
let waitingTimer = null

const AGENT_NAMES = {
  chart: '生成图表',
  report: '生成报表',
  data_table: '数据分析',
  webpage: '网页展示',
}

const LLM_STORAGE_KEY = 'selectedLlmId'

const currentConversationTitle = computed(() => {
  const currentConversation = conversations.value.find((conv) => conv.id === chatStore.conversationId)
  return currentConversation?.title || '智能问答'
})

onMounted(async () => {
  await kbStore.fetchList()
  try {
    const { data } = await llmApi.list()
    llmConfigs.value = data.items
    const savedLlmId = localStorage.getItem(LLM_STORAGE_KEY)
    if (savedLlmId && llmConfigs.value.some((c) => c.id === savedLlmId)) {
      selectedLlm.value = savedLlmId
    } else if (llmConfigs.value.length > 0) {
      selectedLlm.value = llmConfigs.value[0].id
      localStorage.setItem(LLM_STORAGE_KEY, selectedLlm.value)
    }
  } catch {}

  if (selectedKb.value) {
    loadHistory()
  }
})

watch(
  () => chatStore.messages.length,
  () => {
    nextTick(() => {
      if (messagesArea.value) {
        messagesArea.value.scrollTop = messagesArea.value.scrollHeight
      }
    })
  },
)

watch(
  () => chatStore.conversationId,
  (newId) => {
    if (newId) {
      loadHistory()
    }
  },
)

function onKbChange(kbId) {
  localStorage.setItem('lastKbId', kbId)
  newConversation()
  loadHistory()
}

function onLlmChange(llmId) {
  if (llmId) {
    localStorage.setItem(LLM_STORAGE_KEY, llmId)
  }
}

function newConversation() {
  chatStore.reset()
}

async function loadHistory() {
  if (!selectedKb.value) return
  try {
    const { data } = await chatApi.conversations({ kb_id: selectedKb.value })
    conversations.value = data.items
  } catch {}
}

async function loadConversation(convId) {
  try {
    await chatStore.loadConversation(convId)
  } catch {
    ElMessage.error('加载对话失败')
  }
}

async function confirmDelete(convId) {
  try {
    await ElMessageBox.confirm('确定删除该对话吗？删除后无法恢复。', '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await chatApi.delete(convId)
    if (chatStore.conversationId === convId) {
      chatStore.reset()
    }
    loadHistory()
    ElMessage.success('已删除')
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

async function editTitle(conv) {
  try {
    const { value } = await ElMessageBox.prompt('请输入新的对话标题', '修改标题', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputValue: conv.title,
      inputPattern: /^.{1,100}$/,
      inputErrorMessage: '标题长度需在 1-100 个字符之间',
    })
    await chatApi.update(conv.id, { title: value })
    loadHistory()
    ElMessage.success('标题已更新')
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('修改失败')
    }
  }
}

async function handleSend() {
  const query = inputText.value.trim()
  if (!query || !selectedKb.value) {
    ElMessage.warning(selectedKb.value ? '请输入问题' : '请先选择知识库')
    return
  }
  inputText.value = ''

  try {
    const { data: intentData } = await agentApi.detectIntent({
      query,
      llm_config_id: selectedLlm.value,
    })

    if (intentData.agent_type && intentData.agent_type !== 'text') {
      const agentName = AGENT_NAMES[intentData.agent_type] || intentData.agent_type
      try {
        await ElMessageBox.confirm(
          `检测到您的问题适合使用“${agentName}”智能体处理，是否使用？`,
          '智能体推荐',
          {
            confirmButtonText: '使用智能体',
            cancelButtonText: '普通问答',
            type: 'info',
          },
        )
        await executeAgentWithSave(query, intentData.agent_type)
        return
      } catch {
        try {
          await chatStore.sendMessage(query, selectedKb.value, selectedLlm.value, false)
          loadHistory()
        } catch (e) {
          ElMessage.error(`发送失败: ${e.message || '网络错误'}`)
        }
        return
      }
    }
  } catch {}

  try {
    await chatStore.sendMessage(query, selectedKb.value, selectedLlm.value, true)
    loadHistory()
  } catch (e) {
    ElMessage.error(`发送失败: ${e.message || '网络错误'}`)
  }
}

function startWaitingTimer(assistantMsg) {
  waitingSeconds.value = 0
  if (waitingTimer) clearInterval(waitingTimer)
  waitingTimer = setInterval(() => {
    waitingSeconds.value += 1
    if (assistantMsg && assistantMsg.waiting) {
      assistantMsg.waitingSeconds = waitingSeconds.value
    }
  }, 1000)
}

function stopWaitingTimer() {
  if (waitingTimer) {
    clearInterval(waitingTimer)
    waitingTimer = null
  }
}

function formatTime(seconds) {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

async function executeAgentWithSave(query, agentType) {
  chatStore.messages.push({ role: 'user', content: { text: query } })

  const assistantMsg = {
    role: 'assistant',
    content: { text: '请稍候，智能体正在处理...', citations: [] },
    type: agentType,
    confidence: null,
    model: null,
    waiting: true,
  }
  chatStore.messages.push(assistantMsg)
  agentLoading.value = true
  startWaitingTimer(assistantMsg)

  try {
    const { data } = await agentApi.execute({
      query,
      kb_id: selectedKb.value,
      agent_type: agentType,
      llm_config_id: selectedLlm.value,
      conversation_id: chatStore.conversationId,
    })

    assistantMsg.content = data.content
    assistantMsg.type = data.type
    assistantMsg.confidence = data.confidence
    assistantMsg.waiting = false

    if (data.conversation_id) {
      chatStore.conversationId = data.conversation_id
    }

    loadHistory()
    ElMessage.success(`处理完成，耗时 ${formatTime(waitingSeconds.value)}`)
  } catch (e) {
    assistantMsg.content = {
      text: `智能体处理失败: ${e.response?.data?.detail || e.message || '网络错误'}`,
      citations: [],
    }
    assistantMsg.waiting = false
    ElMessage.error('智能体处理失败')
  } finally {
    agentLoading.value = false
    stopWaitingTimer()
  }
}

async function handleAgentCommand(agentType) {
  const query = inputText.value.trim()
  if (!query || !selectedKb.value) {
    ElMessage.warning('请输入问题并选择知识库')
    return
  }
  inputText.value = ''
  await executeAgentWithSave(query, agentType)
}

async function handleSaveShortcut(msg, msgIndex) {
  let userQuery = ''
  for (let index = msgIndex - 1; index >= 0; index -= 1) {
    if (chatStore.messages[index].role === 'user') {
      userQuery = chatStore.messages[index].content?.text || ''
      break
    }
  }

  const title = userQuery.slice(0, 100) || '快捷方式'
  const snapshot = {
    ...msg.content,
    type: msg.type,
  }

  try {
    await shortcutApi.create({
      title,
      query_text: userQuery,
      answer_snapshot: snapshot,
      kb_id: selectedKb.value,
    })
    ElMessage.success('已保存为快捷方式')
  } catch {
    ElMessage.error('保存失败')
  }
}
</script>

<style scoped>
.chat-shell {
  margin: 0;
  width: 100%;
  max-width: 100%;
  height: 100%;
  min-height: 0;
  padding: 18px;
  overflow-x: hidden;
  background:
    radial-gradient(circle at top left, rgba(255, 107, 107, 0.18), transparent 24%),
    radial-gradient(circle at bottom right, rgba(72, 219, 251, 0.18), transparent 25%),
    linear-gradient(135deg, #fff8f1 0%, #f7fbff 52%, #f7fff9 100%);
}

.chat-container {
  display: flex;
  gap: 18px;
  height: 100%;
  min-height: 0;
}

.chat-sidebar {
  width: 300px;
  padding: 18px;
  border-radius: 30px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.72);
  box-shadow: 0 20px 54px rgba(88, 100, 152, 0.14);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.sidebar-top {
  padding: 8px 4px 16px;
}

.sidebar-title {
  font-size: 24px;
  font-weight: 800;
  color: #24304f;
}

.sidebar-subtitle {
  margin-top: 6px;
  font-size: 13px;
  color: #8b95a9;
}

.kb-select {
  width: 100%;
  margin-bottom: 10px;
}

.kb-select :deep(.el-input__wrapper) {
  border-radius: 18px;
  box-shadow: 0 0 0 1px rgba(113, 125, 168, 0.08) inset;
}

.new-chat-btn {
  width: 100%;
  margin-bottom: 14px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(84, 160, 255, 0.14), rgba(127, 90, 240, 0.14));
  color: #3555a8;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;
}

.history-item {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  padding: 10px 12px;
  border-radius: 18px;
  cursor: pointer;
  color: #5d6880;
  background: transparent;
  transition: all 0.22s ease;
}

.history-item:hover {
  background: linear-gradient(135deg, rgba(244, 247, 255, 0.95), rgba(255, 246, 251, 0.95));
}

.history-item.active {
  color: #2647a5;
  background: linear-gradient(135deg, rgba(84, 160, 255, 0.15), rgba(72, 219, 251, 0.15));
  box-shadow: inset 0 0 0 1px rgba(84, 160, 255, 0.18);
}

.history-content {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-actions {
  display: flex;
  gap: 6px;
  opacity: 0;
  transition: opacity 0.2s;
}

.history-item:hover .history-actions {
  opacity: 1;
}

.action-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.edit-icon {
  color: #4f7cff;
}

.edit-icon:hover {
  background: rgba(79, 124, 255, 0.12);
}

.delete-icon {
  color: #ff6b6b;
}

.delete-icon:hover {
  background: rgba(255, 107, 107, 0.12);
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  border-radius: 34px;
  overflow: hidden;
  overflow-x: hidden;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 22px 58px rgba(84, 96, 142, 0.13);
  backdrop-filter: blur(10px);
}

.main-hero {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 24px 28px 18px;
  background:
    radial-gradient(circle at top right, rgba(29, 209, 161, 0.18), transparent 24%),
    linear-gradient(135deg, rgba(255, 249, 242, 0.96), rgba(245, 248, 255, 0.98));
  border-bottom: 1px solid rgba(227, 231, 244, 0.82);
}

.main-hero h2 {
  margin: 0;
  font-size: 28px;
  color: #22304b;
}

.hero-dots {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding-top: 6px;
}

.hero-dots span {
  width: 16px;
  height: 16px;
  border-radius: 999px;
}

.hero-dots span:nth-child(1) {
  background: #ff6b6b;
}

.hero-dots span:nth-child(2) {
  background: #48dbfb;
}

.hero-dots span:nth-child(3) {
  background: #1dd1a1;
}

.messages-area {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 26px 28px 18px;
  background:
    radial-gradient(circle at top left, rgba(84, 160, 255, 0.08), transparent 20%),
    radial-gradient(circle at bottom right, rgba(255, 159, 103, 0.08), transparent 18%),
    linear-gradient(180deg, rgba(251, 252, 255, 0.72), rgba(255, 255, 255, 0.9));
}

.message-row {
  margin-bottom: 18px;
}

.message-row.user {
  display: flex;
  justify-content: flex-end;
}

.message-row.assistant {
  display: flex;
  justify-content: flex-start;
}

.input-area {
  margin: 0 18px 18px;
  padding: 16px 18px 18px;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(225, 229, 242, 0.88);
  box-shadow: 0 14px 34px rgba(77, 91, 140, 0.1);
}

.input-box {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  margin-bottom: 12px;
}

.input-box .el-textarea {
  flex: 1;
}

.input-box :deep(.el-textarea__inner) {
  border-radius: 22px;
  padding: 14px 16px;
  background: linear-gradient(180deg, #fbfdff, #f7f9ff);
  box-shadow: inset 0 0 0 1px rgba(214, 220, 239, 0.88);
}

.send-btn {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  border: 0;
  background: linear-gradient(135deg, #4f7cff, #7f5af0);
  box-shadow: 0 12px 24px rgba(79, 124, 255, 0.28);
}

.input-toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.toolbar-select {
  width: 180px;
}

.toolbar-select :deep(.el-input__wrapper) {
  border-radius: 16px;
}

.agent-btn {
  border-radius: 16px;
  border-color: rgba(79, 124, 255, 0.28);
  color: #3555a8;
}

@media (max-width: 1100px) {
  .chat-container {
    flex-direction: column;
    height: 100%;
  }

  .chat-sidebar {
    width: 100%;
  }

  .chat-main {
    min-height: 0;
  }
}
</style>
