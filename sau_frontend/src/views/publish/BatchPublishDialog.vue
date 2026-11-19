<template>
  <el-dialog
    v-model="publish.batchPublishDialogVisible"
    title="批量发布进度"
    width="500px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
  >
    <div class="publish-progress">
      <el-progress
        :percentage="publish.publishProgress"
        :status="publish.publishProgress === 100 ? 'success' : ''"
      />
      <div v-if="publish.currentPublishingTab" class="current-publishing">
        正在发布：{{ publish.currentPublishingTab.label }}
      </div>

      <!-- 发布结果列表 -->
      <div class="publish-results" v-if="publish.publishResults.length > 0">
        <div
          v-for="(result, index) in publish.publishResults"
          :key="index"
          :class="['result-item', result.status]"
        >
          <el-icon v-if="result.status === 'success'"><Check /></el-icon>
          <el-icon v-else-if="result.status === 'error'"><Close /></el-icon>
          <el-icon v-else><InfoFilled /></el-icon>
          <span class="label">{{ result.label }}</span>
          <span class="message">{{ result.message }}</span>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="publish.cancelBatchPublish" :disabled="publish.publishProgress === 100">
          取消发布
        </el-button>
        <el-button
          type="primary"
          @click="publish.batchPublishDialogVisible = false"
          v-if="publish.publishProgress === 100"
        >
          关闭
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { Check, Close, InfoFilled } from '@element-plus/icons-vue'
import { usePublishContext } from '@/composables/publish/publishContext'

const publish = usePublishContext()
</script>
