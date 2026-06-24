<template>
  <div class="file-uploader">
    <el-upload
      ref="uploadRef"
      :action="uploadUrl"
      name="files"
      multiple
      :accept="acceptTypes"
      :on-success="handleSuccess"
      :on-error="handleError"
      :on-progress="handleProgress"
      :before-upload="beforeUpload"
      :show-file-list="false"
      :disabled="uploading"
    >
      <el-button type="primary" :loading="uploading">
        <el-icon v-if="!uploading"><Upload /></el-icon>
        {{ uploading ? '上传中...' : '上传文档' }}
      </el-button>
    </el-upload>

    <!-- 上传进度对话框 -->
    <el-dialog
      v-model="showProgressDialog"
      title="文档上传进度"
      width="500px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="!hasUploading"
    >
      <div class="progress-container">
        <div
          v-for="(file, index) in uploadFiles"
          :key="index"
          class="file-progress-item"
        >
          <div class="file-info">
            <el-icon :size="18">
              <Document v-if="file.status === 'pending'" />
              <Loading v-else-if="file.status === 'uploading'" class="is-loading" />
              <CircleCheck v-else-if="file.status === 'success'" style="color: #67c23a" />
              <CircleClose v-else-if="file.status === 'error'" style="color: #f56c6c" />
            </el-icon>
            <span class="filename">{{ file.name }}</span>
            <span class="filesize">{{ formatSize(file.size) }}</span>
          </div>

          <!-- 上传进度条 -->
          <el-progress
            v-if="file.status === 'uploading'"
            :percentage="file.uploadProgress"
            :stroke-width="6"
            :show-text="true"
          />

          <!-- 处理状态 -->
          <div v-if="file.status === 'processing'" class="processing-status">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>正在解析文档...</span>
          </div>

          <!-- 完成信息 -->
          <div v-if="file.status === 'success'" class="success-info">
            <span>✓ 上传成功，等待分块</span>
          </div>

          <!-- 错误信息 -->
          <div v-if="file.status === 'error'" class="error-info">
            <span>✗ {{ file.errorMsg || '上传失败' }}</span>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="closeDialog" :disabled="hasUploading">
          {{ hasUploading ? '处理中，请稍候...' : '关闭' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload, Document, Loading, CircleCheck, CircleClose } from '@element-plus/icons-vue'

const props = defineProps({
  kbId: { type: String, required: true },
})

const emit = defineEmits(['uploaded'])

const uploadUrl = computed(() => `/api/v1/kb/${props.kbId}/documents`)
const acceptTypes = '.pdf,.docx,.doc,.csv,.txt,.md'

const uploading = ref(false)
const showProgressDialog = ref(false)
const uploadFiles = ref([])

const hasUploading = computed(() => {
  return uploadFiles.value.some(f => f.status === 'uploading' || f.status === 'processing')
})

function formatSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

function beforeUpload(file) {
  const maxSize = 100 * 1024 * 1024 // 100MB
  if (file.size > maxSize) {
    ElMessage.error(`${file.name} 超过100MB限制`)
    return false
  }

  // 添加到上传列表
  uploadFiles.value.push({
    name: file.name,
    size: file.size,
    status: 'uploading',
    uploadProgress: 0,
    errorMsg: '',
  })

  uploading.value = true
  showProgressDialog.value = true
  return true
}

function handleProgress(event, file) {
  const fileIndex = uploadFiles.value.findIndex(f => f.name === file.name)
  if (fileIndex !== -1) {
    uploadFiles.value[fileIndex].uploadProgress = Math.round(event.percent)
  }
}

function handleSuccess(response, file) {
  const fileIndex = uploadFiles.value.findIndex(f => f.name === file.name)

  if (response && response.results && response.results.length > 0) {
    const result = response.results.find(r => r.filename === file.name)
    if (fileIndex !== -1) {
      if (result && result.status === 'parsed') {
        // 解析成功，等待分块
        uploadFiles.value[fileIndex].status = 'success'
      } else if (result && result.status === 'failed') {
        uploadFiles.value[fileIndex].status = 'error'
        uploadFiles.value[fileIndex].errorMsg = result.error_message || '解析失败'
      } else {
        uploadFiles.value[fileIndex].status = 'success'
      }
    }
  } else if (fileIndex !== -1) {
    uploadFiles.value[fileIndex].status = 'success'
  }

  checkAllComplete()
}

function handleError(error, file) {
  const fileIndex = uploadFiles.value.findIndex(f => f.name === file.name)
  if (fileIndex !== -1) {
    uploadFiles.value[fileIndex].status = 'error'
    uploadFiles.value[fileIndex].errorMsg = error?.message || '上传失败'
  }
  checkAllComplete()
}

function checkAllComplete() {
  const allDone = uploadFiles.value.every(
    f => f.status === 'success' || f.status === 'error'
  )

  if (allDone) {
    uploading.value = false
    const successCount = uploadFiles.value.filter(f => f.status === 'success').length
    const errorCount = uploadFiles.value.filter(f => f.status === 'error').length

    if (errorCount === 0) {
      ElMessage.success(`成功上传 ${successCount} 个文档`)
    } else if (successCount === 0) {
      ElMessage.error(`上传失败 ${errorCount} 个文档`)
    } else {
      ElMessage.warning(`成功 ${successCount} 个，失败 ${errorCount} 个`)
    }

    emit('uploaded')
  }
}

function closeDialog() {
  if (!hasUploading.value) {
    showProgressDialog.value = false
    uploadFiles.value = []
  }
}
</script>

<style scoped>
.file-uploader {
  display: inline-block;
}

.progress-container {
  max-height: 400px;
  overflow-y: auto;
}

.file-progress-item {
  padding: 12px 0;
  border-bottom: 1px solid #ebeef5;
}

.file-progress-item:last-child {
  border-bottom: none;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.filename {
  flex: 1;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.filesize {
  color: #909399;
  font-size: 12px;
}

.processing-status {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #e6a23c;
  font-size: 13px;
}

.success-info {
  color: #67c23a;
  font-size: 13px;
}

.error-info {
  color: #f56c6c;
  font-size: 13px;
}

.is-loading {
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
