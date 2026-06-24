<template>
  <div class="kg-page">
    <div class="kg-header">
      <h2>知识图谱</h2>
      <div class="kg-controls">
        <el-select
          v-model="selectedKbId"
          placeholder="选择知识库"
          @change="loadGraph"
          style="width: 240px"
        >
          <el-option
            v-for="kb in kbList"
            :key="kb.id"
            :label="kb.name"
            :value="kb.id"
          />
        </el-select>
        <el-select
          v-model="typeFilter"
          placeholder="实体类型过滤"
          clearable
          @change="loadGraph"
          style="width: 160px; margin-left: 12px"
        >
          <el-option
            v-for="t in entityTypes"
            :key="t"
            :label="t"
            :value="t"
          />
        </el-select>
        <el-button @click="loadGraph" type="primary" :loading="loading">
          <el-icon><Refresh /></el-icon> 刷新图谱
        </el-button>
        <el-button @click="rebuildGraph" type="warning" :loading="building" :disabled="!selectedKbId" style="margin-left: 8px">
          <el-icon><MagicStick /></el-icon> 重建图谱
        </el-button>
        <el-tag v-if="graphStats" style="margin-left: 12px" type="info">
          {{ graphStats.nodes }} 节点 / {{ graphStats.edges }} 关系
        </el-tag>
      </div>
    </div>

    <div class="kg-main" v-loading="loading">
      <div v-if="!selectedKbId" class="kg-placeholder">
        <el-icon :size="64"><Share /></el-icon>
        <p>请先选择一个知识库，然后点击"刷新图谱"查看知识图谱</p>
        <p class="hint">（需要先上传文档并开启图构建功能）</p>
      </div>

      <div v-else-if="graphError" class="kg-placeholder error">
        <el-icon :size="48"><WarningFilled /></el-icon>
        <p>{{ graphError }}</p>
      </div>

      <div v-else-if="!graphOption" class="kg-placeholder">
        <el-icon :size="48"><WarningFilled /></el-icon>
        <p>该知识库暂无图谱数据</p>
        <p class="hint">点击"重建图谱"自动从文档中提取实体和关系</p>
        <el-button @click="rebuildGraph" type="warning" :loading="building" size="large">
          <el-icon><MagicStick /></el-icon> 重建图谱
        </el-button>
      </div>

      <div v-else class="kg-graph-container">
        <v-chart
          :option="graphOption"
          autoresize
          style="height: calc(100vh - 180px); width: 100%"
          @click="onNodeClick"
        />
      </div>
    </div>

    <!-- Entity detail dialog -->
    <el-dialog v-model="detailVisible" :title="selectedEntity?.name" width="500px">
      <template v-if="selectedEntity">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="类型">{{ selectedEntity.entity_type }}</el-descriptions-item>
          <el-descriptions-item label="关联数">{{ entityRelations.length }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="entityRelations.length" style="margin-top: 16px">
          <h4>关联关系</h4>
          <el-table :data="entityRelations" size="small" max-height="300">
            <el-table-column prop="relation" label="关系" />
            <el-table-column prop="target" label="关联实体" />
          </el-table>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Share, WarningFilled, Refresh, MagicStick } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import api, { kbApi } from '@/api'

use([GraphChart, TitleComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const kbList = ref([])
const selectedKbId = ref('')
const typeFilter = ref('')
const entityTypes = ref([])
const loading = ref(false)
const building = ref(false)
const graphError = ref('')
const graphData = ref(null)
const detailVisible = ref(false)
const selectedEntity = ref(null)
const entityRelations = ref([])

const graphStats = computed(() => {
  if (!graphData.value) return null
  return {
    nodes: graphData.value.nodes?.length || 0,
    edges: graphData.value.links?.length || 0,
  }
})

const graphOption = computed(() => {
  if (!graphData.value || !graphData.value.nodes?.length) return null

  const categories = graphData.value.categories || []
  const nodes = graphData.value.nodes.map(n => ({
    ...n,
    symbolSize: n.symbolSize || 30,
    label: { show: true, fontSize: 11 },
  }))
  const links = graphData.value.links.map(l => ({
    source: l.source,
    target: l.target,
    label: { show: true, formatter: l.label || '' },
    lineStyle: { width: Math.max(1, (l.weight || 1) * 1.5) },
  }))

  return {
    tooltip: {
      formatter: (params) => {
        if (params.dataType === 'node') return `${params.name}<br/>类型: ${params.data.entity_type || '-'}`
        if (params.dataType === 'edge') return `${params.data.label || '关联'}`
        return ''
      },
    },
    legend: [{ data: categories.map(c => c.name), orient: 'vertical', left: 10, top: 20 }],
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      categories,
      nodes,
      links,
      force: {
        repulsion: 300,
        edgeLength: [100, 300],
        gravity: 0.1,
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 5 },
      },
      lineStyle: {
        color: 'source',
        curveness: 0.2,
        width: 1.5,
      },
      label: {
        show: true,
        position: 'right',
        fontSize: 12,
      },
    }],
  }
})

async function loadKbList() {
  try {
    const res = await kbApi.list()
    kbList.value = (res.data.items || []).map(kb => ({
      id: kb.id,
      name: kb.name,
    }))
  } catch (e) {
    console.error('Failed to load KB list', e)
  }
}

async function rebuildGraph() {
  if (!selectedKbId.value) return
  try {
    await ElMessageBox.confirm(
      '将从知识库所有文档中提取实体和关系，构建知识图谱。此过程需要调用LLM，可能需要几分钟。',
      '确认重建图谱',
      { confirmButtonText: '开始构建', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }

  building.value = true
  graphError.value = ''
  try {
    const res = await api.post(`/kb/${selectedKbId.value}/build-graph`)
    const data = res.data
    const totalEntities = data.total_entities || data.results?.reduce((s, r) => s + (r.entities || 0), 0) || 0
    const totalRels = data.total_relations || data.results?.reduce((s, r) => s + (r.relations || 0), 0) || 0
    ElMessage.success(`图谱构建完成！提取 ${totalEntities} 个实体、${totalRels} 条关系`)
    await loadGraph()
  } catch (e) {
    const detail = e.response?.data?.detail || e.message
    if (detail.includes('No LLM configured')) {
      graphError.value = '请先在系统设置中配置LLM模型'
    } else {
      graphError.value = '图谱构建失败: ' + detail
    }
    ElMessage.error(graphError.value)
  } finally {
    building.value = false
  }
}

async function loadGraph() {
  if (!selectedKbId.value) return
  loading.value = true
  graphError.value = ''
  try {
    // Load entity types
    const typesRes = await api.get(`/kb/${selectedKbId.value}/graph/types`)
    entityTypes.value = typesRes.data.types || []

    // Load graph data
    const params = { limit: 300 }
    if (typeFilter.value) params.entity_type = typeFilter.value
    const res = await api.get(`/kb/${selectedKbId.value}/graph`, { params })
    if (res.data.status === 'unavailable') {
      graphError.value = res.data.message || 'Neo4j 图数据库未连接'
      graphData.value = null
    } else {
      graphData.value = res.data
    }
  } catch (e) {
    graphError.value = '加载图谱失败: ' + (e.response?.data?.detail || e.message)
    graphData.value = null
  } finally {
    loading.value = false
  }
}

function onNodeClick(params) {
  if (params.dataType === 'node') {
    selectedEntity.value = {
      id: params.data.id,
      name: params.data.name,
      entity_type: params.data.entity_type || '',
    }
    // Find relations for this entity
    if (graphData.value) {
      const nodeId = params.data.id
      entityRelations.value = graphData.value.links
        .filter(l => l.source === nodeId || l.target === nodeId)
        .map(l => {
          const otherId = l.source === nodeId ? l.target : l.source
          const otherNode = graphData.value.nodes.find(n => n.id === otherId)
          return {
            relation: l.label || '关联',
            target: otherNode?.name || otherId,
          }
        })
    }
    detailVisible.value = true
  }
}

onMounted(() => {
  loadKbList()
})
</script>

<style scoped>
.kg-page {
  padding: 16px 24px;
  height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
}
.kg-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.kg-header h2 { margin: 0; font-size: 20px; }
.kg-controls { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
.kg-main {
  flex: 1;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  background: #fff;
  overflow: hidden;
}
.kg-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
  gap: 12px;
}
.kg-placeholder.error { color: #f56c6c; }
.kg-placeholder .hint { font-size: 12px; color: #c0c4cc; }
.kg-graph-container { width: 100%; height: 100%; }
</style>
