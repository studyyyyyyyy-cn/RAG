import { defineStore } from 'pinia'
import { ref } from 'vue'
import { chatApi } from '@/api'
import { fetchEventSource } from '@microsoft/fetch-event-source'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const conversationId = ref(null)
  const streaming = ref(false)
  const currentMetadata = ref(null)

  function reset() {
    messages.value = []
    conversationId.value = null
    currentMetadata.value = null
  }

  async function loadConversation(id) {
    const { data } = await chatApi.conversation(id)
    conversationId.value = id
    messages.value = data.messages.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      type: m.type,
      confidence: m.confidence,
      model: m.model_used,
    }))
  }

  async function sendMessage(query, kbId, llmConfigId = null, enableAgent = true) {
    messages.value.push({ role: 'user', content: { text: query } })

    const assistantMsg = {
      role: 'assistant',
      content: { text: '请等待...', citations: [] },
      confidence: null,
      model: null,
      type: 'text',
    }
    messages.value.push(assistantMsg)

    streaming.value = true

    try {
      await fetchEventSource('/api/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          kb_id: kbId,
          conversation_id: conversationId.value,
          llm_config_id: llmConfigId,
          stream: true,
          enable_agent: enableAgent,
        }),
        onmessage(ev) {
          const data = JSON.parse(ev.data)
          const lastMsg = messages.value[messages.value.length - 1]
          if (!lastMsg) return

          switch (ev.event) {
            case 'metadata':
              currentMetadata.value = data
              lastMsg.confidence = data.confidence
              lastMsg.model = data.model_used
              lastMsg.content.citations = data.citations || []
              lastMsg.type = data.agent_type || 'text'
              if (lastMsg.content.text === '请等待...') {
                lastMsg.content.text = ''
              }
              break
            case 'text_chunk':
              if (lastMsg.content.text === '请等待...') {
                lastMsg.content.text = ''
              }
              lastMsg.content.text += data.text
              break
            case 'agent_result':
              lastMsg.type = data.type || lastMsg.type || 'text'
              lastMsg.content = {
                ...(lastMsg.content || {}),
                ...(data.content || {}),
              }
              break
            case 'complete':
              conversationId.value = data.conversation_id
              lastMsg.id = data.message_id
              break
            case 'error':
              lastMsg.content.text = '处理出错: ' + (data.detail || '未知错误')
              break
          }
        },
        onerror(err) {
          console.error('SSE error:', err)
          const lastMsg = messages.value[messages.value.length - 1]
          if (lastMsg && lastMsg.content.text === '请等待...') {
            lastMsg.content.text = '处理出错，请稍后重试'
          }
          throw err
        },
      })
    } catch (err) {
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg && lastMsg.content.text === '请等待...') {
        lastMsg.content.text = '处理出错，请稍后重试'
      }
    } finally {
      streaming.value = false
    }
  }

  return { messages, conversationId, streaming, currentMetadata, reset, loadConversation, sendMessage }
})
