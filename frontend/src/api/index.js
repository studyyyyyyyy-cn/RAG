import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

export const kbApi = {
  list: (params) => api.get('/kb', { params }),
  get: (id) => api.get(`/kb/${id}`),
  create: (data) => api.post('/kb', data),
  update: (id, data) => api.put(`/kb/${id}`, data),
  delete: (id) => api.delete(`/kb/${id}`),
}

export const docApi = {
  list: (kbId, params) => api.get(`/kb/${kbId}/documents`, { params }),
  upload: (kbId, formData) =>
    api.post(`/kb/${kbId}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    }),
  delete: (kbId, docId) => api.delete(`/kb/${kbId}/documents/${docId}`),
  status: (kbId, docId) => api.get(`/kb/${kbId}/documents/${docId}/status`),
  chunks: (kbId, docId, params) => api.get(`/kb/${kbId}/documents/${docId}/chunks`, { params }),
  chunk: (kbId, chunkId) => api.get(`/kb/${kbId}/chunks/${chunkId}`),
  executeChunk: (kbId, docId, chunkMethod) =>
    api.post(`/kb/${kbId}/documents/${docId}/chunk?chunk_method=${chunkMethod}`, null, {
      timeout: 300000,
    }),
  chunkBatch: (kbId, docIds, chunkMethod, params = null) =>
    api.post(
      `/kb/${kbId}/documents/chunk-batch`,
      {
        doc_ids: docIds,
        chunk_method: chunkMethod,
        params,
      },
      {
        timeout: 600000,
      },
    ),
}

export const chatApi = {
  send: (data) => api.post('/chat', { ...data, stream: false }),
  conversations: (params) => api.get('/conversations', { params }),
  conversation: (id) => api.get(`/conversations/${id}`),
  update: (id, data) => api.put(`/conversations/${id}`, data),
  delete: (id) => api.delete(`/conversations/${id}`),
  testChat: (kbId, data) => api.post(`/kb/${kbId}/test-chat`, data, { timeout: 300000 }),
}

export const agentApi = {
  execute: (data) => api.post('/agent/execute', data, { timeout: 300000 }),
  detectIntent: (data) => api.post('/agent/detect-intent', data),
  chart: (data) => api.post('/agent/chart', data, { timeout: 300000 }),
  report: (data) => api.post('/agent/report', data, { timeout: 300000 }),
  analyze: (data) => api.post('/agent/analyze', data, { timeout: 300000 }),
}

export const shortcutApi = {
  list: (params) => api.get('/shortcuts', { params }),
  get: (id) => api.get(`/shortcuts/${id}`),
  create: (data) => api.post('/shortcuts', data),
  update: (id, data) => api.put(`/shortcuts/${id}`, data),
  delete: (id) => api.delete(`/shortcuts/${id}`),
  refresh: (id) => api.post(`/shortcuts/${id}/refresh`),
  exportMd: (id) => api.get(`/shortcuts/${id}/export-md`, { responseType: 'blob' }),
}

export const messageApi = {
  exportMd: (messageId) => api.get(`/messages/${messageId}/export-md`, { responseType: 'blob' }),
}

export const llmApi = {
  list: () => api.get('/llm/configs'),
  create: (data) => api.post('/llm/configs', data),
  update: (id, data) => api.put(`/llm/configs/${id}`, data),
  delete: (id) => api.delete(`/llm/configs/${id}`),
  test: (data) => api.post('/llm/configs/test', data),
}

export default api
