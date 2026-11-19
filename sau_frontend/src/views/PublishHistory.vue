<template>
  <div class="publish-history">
    <div class="history-container">
      <div class="toolbar">
        <h3>发布记录</h3>
        <el-button type="info" @click="fetchLogs" :loading="false">
          <el-icon :class="{ 'is-loading': loading }"><Refresh /></el-icon>
          <span v-if="loading">刷新中</span>
        </el-button>
      </div>

      <el-table v-if="logs.length > 0" :data="logs" style="width: 100%">
        <el-table-column prop="publishTime" label="发布时间" width="180" />
        <el-table-column prop="userName" label="名称" width="140" />
        <el-table-column label="平台" width="100">
          <template #default="scope">
            <el-tag :type="getPlatformTagType(scope.row.type)" effect="plain">
              {{ getPlatformName(scope.row.type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
        <el-table-column label="视频" min-width="200" show-overflow-tooltip>
          <template #default="scope">
            {{ formatFileNames(scope.row.fileList) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)" effect="plain">
              {{ getStatusText(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="说明" min-width="180" show-overflow-tooltip />
      </el-table>

      <div v-else class="empty-data">
        <el-empty description="暂无发布记录" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { publishApi } from '@/api/publish'
import { getPlatformName } from '@/composables/publish/usePublishForm'

// 发布记录列表（接口已按时间倒序返回）
const logs = ref([])
const loading = ref(false)

// 平台标签颜色
const platformTagTypes = { 3: 'danger', 4: 'success', 2: 'warning', 1: 'info' }

const getPlatformTagType = (type) => platformTagTypes[type] || 'info'

// 发布状态：0 发布中 1 成功 2 失败
const getStatusType = (status) => {
  if (status === 1) return 'success'
  if (status === 2) return 'danger'
  return 'info'
}

const getStatusText = (status) => {
  if (status === 1) return '成功'
  if (status === 2) return '失败'
  return '发布中'
}

// 去掉上传时添加的 UUID 前缀，便于阅读
const formatFileNames = (fileList) => {
  return (fileList || [])
    .map(name => name.split('_').slice(1).join('_') || name)
    .join('、')
}

// 获取发布记录
const fetchLogs = async () => {
  if (loading.value) return
  loading.value = true
  try {
    const res = await publishApi.getPublishLogs()
    if (res.code === 200 && res.data) {
      logs.value = res.data
    }
  } catch (error) {
    console.error('获取发布记录失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchLogs()
})
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.publish-history {
  .history-container {
    background-color: var(--el-bg-color);
    border-radius: 4px;
    box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
    padding: 20px;

    .toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;

      h3 {
        margin: 0;
        font-size: 16px;
        font-weight: 500;
        color: var(--el-text-color-primary);
      }

      .el-icon.is-loading {
        animation: rotate 1s linear infinite;
      }
    }

    .empty-data {
      padding: 40px 0;
    }
  }
}
</style>
