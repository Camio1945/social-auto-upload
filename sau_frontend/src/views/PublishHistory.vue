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
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="scope">
            <el-button
              v-if="scope.row.status === 2"
              size="small"
              type="primary"
              :loading="republishingId === scope.row.id"
              @click="retryPublish(scope.row)"
            >
              重新发布
            </el-button>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>

      <div v-else class="empty-data">
        <el-empty description="暂无发布记录" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { publishApi } from '@/api/publish'
import { accountApi } from '@/api/account'
import { getPlatformName } from '@/composables/publish/usePublishForm'

// 发布记录列表（接口已按时间倒序返回）
const logs = ref([])
const loading = ref(false)

// 正在重新发布的记录 id
const republishingId = ref(null)

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

// 查找记录对应的当前账号（按名称 + 平台匹配，取最新 cookie）
const findCurrentAccount = async (row) => {
  const res = await accountApi.getAccounts()
  const accounts = (res.data || []).map(item => ({
    type: item[1],
    filePath: item[2],
    name: item[3],
    status: item[4]
  }))
  return accounts.find(item => item.name === row.userName && item.type === row.type) || null
}

// 构造单平台重发数据；话题与原创设置未记录，按空值重发
const buildRetryPayload = (row, account) => ({
  type: row.type,
  title: row.title,
  userName: row.userName,
  tags: [],
  fileList: row.fileList,
  accountList: [account.filePath],
  category: 0,
  productLink: '',
  productTitle: '',
  isDraft: false
})

// 重新发布单条失败记录
const retryPublish = async (row) => {
  if (republishingId.value !== null) return
  republishingId.value = row.id
  try {
    const account = await findCurrentAccount(row)
    if (!account) {
      ElMessage.error('未找到该名称在对应平台的账号，请先在账号管理中添加')
      return
    }
    if (account.status !== 1) {
      ElMessage.error('该账号状态异常，请先在账号管理中重新登录')
      return
    }
    await publishApi.retryPublish(buildRetryPayload(row, account))
    ElMessage.success('已重新提交发布，完成后请刷新查看结果')
    await fetchLogs()
  } catch (error) {
    console.error('重新发布失败:', error)
  } finally {
    republishingId.value = null
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
