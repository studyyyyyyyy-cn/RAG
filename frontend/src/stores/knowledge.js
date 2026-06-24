import { defineStore } from 'pinia'
import { ref } from 'vue'
import { kbApi } from '@/api'

export const useKnowledgeStore = defineStore('knowledge', () => {
  const knowledgeBases = ref([])
  const currentKB = ref(null)
  const loading = ref(false)
  const total = ref(0)

  async function fetchList(page = 1, pageSize = 20) {
    loading.value = true
    try {
      const { data } = await kbApi.list({ page, page_size: pageSize })
      knowledgeBases.value = data.items
      total.value = data.total
    } finally {
      loading.value = false
    }
  }

  async function fetchOne(id) {
    const { data } = await kbApi.get(id)
    currentKB.value = data
    return data
  }

  async function create(payload) {
    const { data } = await kbApi.create(payload)
    await fetchList()
    return data
  }

  async function remove(id) {
    await kbApi.delete(id)
    await fetchList()
  }

  return { knowledgeBases, currentKB, loading, total, fetchList, fetchOne, create, remove }
})
