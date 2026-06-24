<template>
  <el-card class="shortcut-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <div class="title-row">
          <el-icon v-if="shortcut.is_pinned" class="pin-icon"><Star /></el-icon>
          <span class="title" @click="$emit('view', shortcut)">{{ shortcut.title }}</span>
        </div>
        <el-dropdown trigger="click">
          <el-icon class="more-btn"><MoreFilled /></el-icon>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="$emit('view', shortcut)">查看详情</el-dropdown-item>
              <el-dropdown-item v-if="isReportType" @click="$emit('exportMd', shortcut.id)">导出MD</el-dropdown-item>
              <el-dropdown-item v-if="isReportType" @click="$emit('exportHtml', shortcut.id)">导出HTML</el-dropdown-item>
              <el-dropdown-item @click="$emit('pin', shortcut)">{{ shortcut.is_pinned ? '取消置顶' : '置顶' }}</el-dropdown-item>
              <el-dropdown-item divided @click="$emit('delete', shortcut.id)" style="color: #f56c6c">删除</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </template>

    <div class="accent-bar"></div>
    <p class="query-text">{{ shortcut.query_text }}</p>

    <div class="card-meta">
      <div class="tags" v-if="shortcut.tags?.length">
        <el-tag v-for="tag in shortcut.tags" :key="tag" size="small" type="info">{{ tag }}</el-tag>
      </div>
      <span class="time">{{ formatDate(shortcut.created_at) }}</span>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'
import { MoreFilled, Star } from '@element-plus/icons-vue'

const props = defineProps({
  shortcut: { type: Object, required: true },
})

defineEmits(['delete', 'pin', 'view', 'exportMd', 'exportHtml'])

const isReportType = computed(() => {
  const snapshot = props.shortcut.answer_snapshot
  return snapshot?.type === 'report' || snapshot?.html_content
})

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.shortcut-card {
  margin-bottom: 18px;
  cursor: pointer;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(247, 251, 255, 0.94));
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.pin-icon {
  color: #f5a623;
}

.title {
  font-weight: 700;
  font-size: 15px;
  color: #26324e;
}

.title:hover {
  color: #4f7cff;
}

.more-btn {
  cursor: pointer;
  color: #9099ad;
}

.accent-bar {
  width: 64px;
  height: 8px;
  border-radius: 999px;
  margin-bottom: 16px;
  background: linear-gradient(135deg, #ff6b6b, #48dbfb, #1dd1a1);
}

.query-text {
  color: #5e6880;
  font-size: 14px;
  line-height: 1.8;
  margin-bottom: 14px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.time {
  font-size: 12px;
  color: #9ca5b6;
}
</style>
