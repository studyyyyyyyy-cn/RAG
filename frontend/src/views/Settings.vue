<template>
  <div class="app-page">
    <div class="page-hero">
      <div>
        <p class="page-eyebrow">System Control</p>
        <h2>系统设置</h2>
        <p>统一管理 LLM 配置与嵌入模型信息，用更清晰的面板关系承载连接测试、默认模型和错误反馈。</p>
      </div>
    </div>

    <el-tabs type="border-card">
      <el-tab-pane label="LLM 模型配置">
        <div class="section-header">
          <span>已配置的模型</span>
          <el-button type="primary" size="small" @click="showLlmDialog = true">
            <el-icon><Plus /></el-icon> 添加模型
          </el-button>
        </div>

        <el-table :data="llmConfigs" stripe>
          <el-table-column prop="display_name" label="名称" width="180" />
          <el-table-column prop="provider" label="提供商" width="120">
            <template #default="{ row }">
              <el-tag size="small">{{ row.provider }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="model_name" label="模型" width="220" />
          <el-table-column label="API Key" width="100">
            <template #default="{ row }">
              <el-tag :type="row.has_api_key ? 'success' : 'info'" size="small">
                {{ row.has_api_key ? '已配置' : '无' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="默认" width="90">
            <template #default="{ row }">
              <el-tag v-if="row.is_default" type="warning" size="small">默认</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="170">
            <template #default="{ row }">
              <el-button text size="small" @click="handleSetDefault(row.id)" v-if="!row.is_default">设为默认</el-button>
              <el-button text size="small" type="danger" @click="handleDeleteLlm(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="Embedding 模型">
        <div class="soft-panel">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="默认模型">BAAI/bge-m3</el-descriptions-item>
            <el-descriptions-item label="向量维度">1024</el-descriptions-item>
            <el-descriptions-item label="特性">同时生成 Dense + Sparse 向量，支持混合检索</el-descriptions-item>
            <el-descriptions-item label="语言">中文 + 英文 多语言</el-descriptions-item>
          </el-descriptions>
          <el-alert title="Embedding 模型在创建知识库时选择，每个知识库可独立配置" type="info" show-icon style="margin-top: 16px" />
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="showLlmDialog" title="添加 LLM 模型" width="540px">
      <el-form :model="llmForm" label-width="100px">
        <el-form-item label="提供商" required>
          <el-select v-model="llmForm.provider" @change="handleProviderChange" style="width: 100%">
            <el-option label="OpenAI" value="openai" />
            <el-option label="Anthropic" value="anthropic" />
            <el-option label="Anthropic 中转服务" value="proxy_anthropic" />
            <el-option label="DeepSeek" value="deepseek" />
            <el-option label="Ollama (本地)" value="ollama" />
            <el-option label="智谱 GLM" value="zhipu" />
            <el-option label="通义千问" value="qwen" />
            <el-option label="vLLM (自部署)" value="vllm" />
            <el-option label="中转服务 (OpenAI格式)" value="proxy_openai" />
            <el-option label="中转服务 (自定义)" value="proxy_custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型名" required>
          <el-input v-model="llmForm.model_name" placeholder="e.g. gpt-4o" />
        </el-form-item>
        <el-form-item label="显示名称" required>
          <el-input v-model="llmForm.display_name" placeholder="e.g. GPT-4o" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="llmForm.api_key" type="password" show-password placeholder="本地模型可留空" />
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="llmForm.base_url" placeholder="自定义 API 地址 (可选)" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="llmForm.is_default" />
        </el-form-item>
      </el-form>

      <div v-if="testResult" class="test-result" :class="testResult.status">
        <el-alert
          :title="testResult.status === 'ok' ? '连接成功' : '连接失败'"
          :type="testResult.status === 'ok' ? 'success' : 'error'"
          :description="testResult.detail || testResult.response"
          show-icon
          :closable="false"
        />
        <div v-if="testResult.trace" class="error-trace">
          <pre>{{ testResult.trace }}</pre>
        </div>
      </div>

      <template #footer>
        <el-button @click="handleTestLlm" :loading="testing">测试连接</el-button>
        <el-button type="primary" @click="handleAddLlm" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { llmApi } from '@/api'

const llmConfigs = ref([])
const showLlmDialog = ref(false)
const testing = ref(false)
const saving = ref(false)

const llmForm = ref({
  provider: 'openai',
  model_name: '',
  display_name: '',
  api_key: '',
  base_url: '',
  is_default: false,
})

const providerDefaults = {
  openai: { base_url: '', model_name: 'gpt-4o' },
  anthropic: { base_url: '', model_name: 'claude-opus-4-6' },
  proxy_anthropic: { base_url: 'https://api.proxy.com', model_name: 'claude-opus-4-6' },
  deepseek: { base_url: 'https://api.deepseek.com', model_name: 'deepseek-chat' },
  ollama: { base_url: 'http://localhost:11434', model_name: 'qwen2.5:7b' },
  zhipu: { base_url: 'https://open.bigmodel.cn/api/paas/v4', model_name: 'glm-4' },
  qwen: { base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model_name: 'qwen-max' },
  vllm: { base_url: 'http://localhost:8001/v1', model_name: 'custom-model' },
  proxy_openai: { base_url: 'https://api.proxy.com/v1', model_name: 'gpt-4o' },
  proxy_custom: { base_url: 'https://api.proxy.com', model_name: 'custom-model' },
}

const testResult = ref(null)

onMounted(loadConfigs)

async function loadConfigs() {
  const { data } = await llmApi.list()
  llmConfigs.value = data.items
}

function handleProviderChange(provider) {
  const defaults = providerDefaults[provider] || {}
  llmForm.value.base_url = defaults.base_url || ''
  llmForm.value.model_name = defaults.model_name || ''
  llmForm.value.display_name = `${provider} - ${defaults.model_name || ''}`
}

async function handleTestLlm() {
  testing.value = true
  testResult.value = null
  try {
    const { data } = await llmApi.test(llmForm.value)
    testResult.value = data
    if (data.status === 'ok') {
      ElMessage.success(`连接成功: ${(data.response || '').slice(0, 50)}`)
    } else {
      ElMessage.error(`连接失败: ${data.detail || ''}`)
    }
  } catch (e) {
    testResult.value = { status: 'error', detail: e.message }
    ElMessage.error(`测试失败: ${e.message}`)
  } finally {
    testing.value = false
  }
}

async function handleAddLlm() {
  if (!llmForm.value.model_name || !llmForm.value.display_name) {
    ElMessage.warning('请填写模型名和显示名称')
    return
  }
  saving.value = true
  try {
    await llmApi.create(llmForm.value)
    showLlmDialog.value = false
    llmForm.value = { provider: 'openai', model_name: '', display_name: '', api_key: '', base_url: '', is_default: false }
    ElMessage.success('已添加')
    loadConfigs()
  } catch {
    ElMessage.error('添加失败')
  } finally {
    saving.value = false
  }
}

async function handleSetDefault(id) {
  await llmApi.update(id, { is_default: true })
  ElMessage.success('已设为默认')
  loadConfigs()
}

async function handleDeleteLlm(id) {
  await ElMessageBox.confirm('确定删除此模型配置？', '确认')
  await llmApi.delete(id)
  loadConfigs()
}
</script>

<style scoped>
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  font-weight: 700;
  color: #26324e;
}

.test-result {
  margin: 16px 0;
  padding: 12px;
  border-radius: 18px;
}

.test-result.ok {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
}

.test-result.error {
  background: #fff2f0;
  border: 1px solid #ffccc7;
}

.error-trace {
  margin-top: 12px;
  padding: 12px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 16px;
  overflow: auto;
  max-height: 300px;
}

.error-trace pre {
  margin: 0;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
