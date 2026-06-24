<template>
  <div class="app-page">
    <div class="page-hero">
      <div>
        <p class="page-eyebrow">Knowledge Hub</p>
        <h2>知识库管理</h2>
        <p>统一管理知识库、文档入口与问答启动链路，并为不同类型文档选择更合适的分块策略。</p>
      </div>
      <el-button type="primary" size="large" class="hero-btn" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon> 新建知识库
      </el-button>
    </div>

    <el-row :gutter="18">
      <el-col v-for="kb in store.knowledgeBases" :key="kb.id" :span="8">
        <el-card class="kb-card" shadow="hover">
          <template #header>
            <div class="kb-card-header">
              <div>
                <div class="kb-name">{{ kb.name }}</div>
                <div class="kb-meta-line">向量模型 · {{ kb.embedding_model }}</div>
              </div>
              <el-dropdown trigger="click">
                <el-icon class="more-btn"><MoreFilled /></el-icon>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="$router.push(`/knowledge/${kb.id}/documents`)">管理文档</el-dropdown-item>
                    <el-dropdown-item @click="$router.push({ path: '/chat', query: { kb_id: kb.id } })">开始问答</el-dropdown-item>
                    <el-dropdown-item divided style="color: #f56c6c" @click="handleDelete(kb.id)">删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>

          <p class="kb-desc">{{ kb.description || '暂无描述' }}</p>

          <div class="kb-badges">
            <el-tag effect="dark" round class="count-tag">{{ kb.doc_count || 0 }} 篇文档</el-tag>
            <el-tag round type="info">Chunk {{ kb.chunk_size }}</el-tag>
          </div>

          <div class="kb-actions">
            <el-button size="small" @click="$router.push(`/knowledge/${kb.id}/documents`)">
              <el-icon><Document /></el-icon> 文档
            </el-button>
            <el-button size="small" type="primary" @click="$router.push({ path: '/chat', query: { kb_id: kb.id } })">
              <el-icon><ChatDotRound /></el-icon> 问答
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-empty v-if="!store.loading && store.knowledgeBases.length === 0" description="暂无知识库，点击上方按钮创建" />

    <el-dialog v-model="showCreateDialog" title="新建知识库" width="520px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="createForm.name" placeholder="输入知识库名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="描述知识库用途" />
        </el-form-item>
        <el-form-item label="Embedding">
          <el-select v-model="createForm.embedding_model" style="width: 100%">
            <el-option label="BGE-M3 (推荐 - 中英双语)" value="BAAI/bge-m3" />
            <el-option label="BGE-Large-ZH (纯中文)" value="BAAI/bge-large-zh-v1.5" />
          </el-select>
        </el-form-item>
        <el-form-item label="分块大小">
          <div class="chunk-size-row">
            <el-input-number v-model="createForm.chunk_size" :min="128" :max="2048" :step="64" />
            <el-tooltip content="查看分块大小对当前各分块方式的影响" placement="top">
              <el-button class="help-btn" circle text @click="showChunkSizeHelp = true">?</el-button>
            </el-tooltip>
          </div>
          <span class="form-tip">tokens</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showChunkSizeHelp" title="分块大小影响说明" width="760px">
      <div class="help-content">
        <p class="help-intro">
          “分块大小”不会影响文档上传本身，只会在文档上传完成后、执行分块时，作为该知识库默认的
          <code>chunk_size</code> 参数参与分块。
        </p>

        <div class="help-section">
          <div class="help-title">当前系统中明显受影响的分块方式</div>
          <div class="help-item">
            <strong>朴素分块 `naive`</strong>
            <span>直接按固定长度切分。数值越小，分块越细；数值越大，单块内容越长。</span>
          </div>
          <div class="help-item">
            <strong>通用分块 `general`</strong>
            <span>按通用长度策略切分，最直接受该参数影响。它决定每个分块大致容纳多少内容。</span>
          </div>
          <div class="help-item">
            <strong>书籍分块 `book`</strong>
            <span>会先按章节结构切分，再参考分块大小控制单块上限；值越大，单章内容更不容易继续拆开。</span>
          </div>
        </div>

        <div class="help-section">
          <div class="help-title">部分受影响的分块方式</div>
          <div class="help-item">
            <strong>论文分块 `paper`</strong>
            <span>主要先按论文结构切分，如摘要、方法、结论等，分块大小不是第一控制因素，但会间接影响最终块长度。</span>
          </div>
          <div class="help-item">
            <strong>简历分块 `resume`</strong>
            <span>主要按简历模块切分，如教育经历、工作经历、项目经历等，通常先看结构，再次参考块大小。</span>
          </div>
          <div class="help-item">
            <strong>表格分块 `table`</strong>
            <span>当前主要按表格行或表格结构切分，不是严格按固定长度切，所以影响相对较弱。</span>
          </div>
        </div>

        <div class="help-section">
          <div class="help-title">基本不依赖该数值的分块方式</div>
          <div class="help-item">
            <strong>问答分块 `qa`</strong>
            <span>主要按问答对、键值对或编号问答切分，不按固定 chunk_size 直接切。</span>
          </div>
        </div>

        <div class="help-section">
          <div class="help-title">使用建议</div>
          <div class="help-item">
            <strong>256 - 512</strong>
            <span>适合通用文档、FAQ、说明书等，希望检索更精确的场景，但会产生更多分块。</span>
          </div>
          <div class="help-item">
            <strong>768 - 1024</strong>
            <span>适合书籍、长篇说明、长章节类文档，但也更容易把无关内容带进单个分块。</span>
          </div>
          <div class="help-item">
            <strong>默认值 512</strong>
            <span>对大多数使用朴素分块、通用分块的知识库来说，是比较稳妥的起点。</span>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useKnowledgeStore } from '@/stores/knowledge'

const store = useKnowledgeStore()
const showCreateDialog = ref(false)
const showChunkSizeHelp = ref(false)
const creating = ref(false)

const createForm = ref({
  name: '',
  description: '',
  embedding_model: 'BAAI/bge-m3',
  chunk_size: 512,
  chunk_overlap: 64,
})

onMounted(() => store.fetchList())

async function handleCreate() {
  if (!createForm.value.name) {
    ElMessage.warning('请输入知识库名称')
    return
  }

  creating.value = true
  try {
    await store.create(createForm.value)
    showCreateDialog.value = false
    createForm.value = {
      name: '',
      description: '',
      embedding_model: 'BAAI/bge-m3',
      chunk_size: 512,
      chunk_overlap: 64,
    }
    ElMessage.success('知识库创建成功')
  } catch (e) {
    ElMessage.error(`创建失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    creating.value = false
  }
}

async function handleDelete(id) {
  await ElMessageBox.confirm(
    '删除知识库将同时删除所有文档和向量数据，此操作不可撤销。',
    '确认删除',
    { type: 'warning' },
  )

  try {
    await store.remove(id)
    ElMessage.success('已删除')
  } catch {
    ElMessage.error('删除失败')
  }
}
</script>

<style scoped>
.hero-btn {
  align-self: center;
  border: 0;
  background: linear-gradient(135deg, #4f7cff, #7f5af0);
  box-shadow: 0 14px 28px rgba(79, 124, 255, 0.24);
}

.kb-card {
  margin-bottom: 18px;
  min-height: 250px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(247, 250, 255, 0.94));
}

.kb-card :deep(.el-card__body) {
  padding-top: 8px;
}

.kb-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.kb-name {
  font-weight: 800;
  font-size: 18px;
  color: #26324e;
}

.kb-meta-line {
  margin-top: 6px;
  font-size: 12px;
  color: #8b95aa;
}

.more-btn {
  cursor: pointer;
  color: #8993a8;
}

.kb-desc {
  min-height: 64px;
  line-height: 1.8;
  color: #5e6880;
}

.kb-badges {
  display: flex;
  gap: 8px;
  margin: 14px 0 16px;
}

.count-tag {
  background: linear-gradient(135deg, #ff8a5b, #ffb347) !important;
  border: 0;
}

.kb-actions {
  display: flex;
  gap: 10px;
}

.chunk-size-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.form-tip {
  margin-left: 8px;
  color: #909399;
  font-size: 13px;
}

.help-btn {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  color: #4f7cff;
  background: rgba(79, 124, 255, 0.08);
  border: 1px solid rgba(79, 124, 255, 0.18);
  font-weight: 700;
}

.help-btn:hover {
  background: rgba(79, 124, 255, 0.14);
}

.help-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  color: #556079;
  line-height: 1.8;
}

.help-intro {
  margin: 0;
  padding: 14px 16px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(247, 250, 255, 0.98), rgba(255, 248, 251, 0.96));
  border: 1px solid rgba(225, 231, 245, 0.9);
}

.help-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.help-title {
  font-size: 15px;
  font-weight: 700;
  color: #26324e;
}

.help-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(248, 250, 255, 0.9);
  border: 1px solid rgba(227, 232, 244, 0.92);
}

.help-item strong {
  color: #2f3b58;
}
</style>
