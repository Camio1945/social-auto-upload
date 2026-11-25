<template>
  <div class="account-management">
    <div class="account-tabs">
      <div class="account-search">
        <el-input
          v-model="searchKeyword"
          placeholder="输入名称或账号搜索"
          prefix-icon="Search"
          clearable
        />
        <div class="action-buttons">
          <el-button type="primary" @click="handleAddAccount">添加账号</el-button>
          <el-button type="info" @click="fetchAccounts" :loading="false">
            <el-icon :class="{ 'is-loading': appStore.isAccountRefreshing }"><Refresh /></el-icon>
            <span v-if="appStore.isAccountRefreshing">刷新中</span>
          </el-button>
        </div>
      </div>

      <el-alert
        v-if="abnormalAccounts.length"
        class="status-alert"
        type="warning"
        :closable="false"
        show-icon
        title="存在 Cookie 失效的账号"
        :description="abnormalDescription"
      />

      <el-tabs v-model="activeTab" class="account-tabs-nav">
        <el-tab-pane
          v-for="tab in platformTabs"
          :key="tab.name"
          :label="tab.label"
          :name="tab.name"
        >
          <div class="account-list-container">
            <div v-if="visibleAccounts.length > 0" class="account-list">
              <AccountTable
                :accounts="visibleAccounts"
                @open="handleOpenAccount"
                @relogin="handleReLogin"
                @edit="handleEdit"
                @download="handleDownloadCookie"
                @upload="handleUploadCookie"
                @delete="handleDelete"
                @status-click="handleStatusClick"
              />
            </div>
            <div v-else class="empty-data">
              <el-empty :description="tab.emptyText" />
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 添加/编辑账号对话框 -->
    <AccountDialog
      v-model="dialogVisible"
      :type="dialogType"
      :form="accountForm"
      :rules="rules"
      :name-options="availableNameOptions"
      :name-hint="nameHint"
      :sse-connecting="sseConnecting"
      :qr-code-data="qrCodeData"
      :login-status="loginStatus"
      @submit="handleDialogSubmit"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import AccountTable from './account/AccountTable.vue'
import AccountDialog from './account/AccountDialog.vue'
import { useAccountStatus } from '@/composables/useAccountStatus'
import { useAccountDialog } from '@/composables/useAccountDialog'

// 当前激活的标签页
const activeTab = ref('all')

// 搜索关键词
const searchKeyword = ref('')

// 标签页与平台的对应关系
const platformTabs = [
  { name: 'all', label: '全部', platform: '', emptyText: '暂无账号数据' },
  { name: 'douyin', label: '抖音', platform: '抖音', emptyText: '暂无抖音账号数据' },
  { name: 'kuaishou', label: '快手', platform: '快手', emptyText: '暂无快手账号数据' },
  { name: 'channels', label: '视频号', platform: '视频号', emptyText: '暂无视频号账号数据' },
  { name: 'xiaohongshu', label: '小红书', platform: '小红书', emptyText: '暂无小红书账号数据' }
]

// 账号列表加载与状态校验
const { accountStore, appStore, nameOptions, fetchNameOptions, fetchAccounts } = useAccountStatus()

// 添加账号时默认选中当前标签页对应的平台
const getDefaultPlatform = () => {
  const current = platformTabs.find(tab => tab.name === activeTab.value)
  return current ? current.platform : ''
}

// 对话框状态与操作（新增、编辑、删除、Cookie、扫码登录）
const {
  dialogVisible,
  dialogType,
  accountForm,
  rules,
  sseConnecting,
  qrCodeData,
  loginStatus,
  availableNameOptions,
  nameHint,
  handleAddAccount,
  handleEdit,
  handleReLogin,
  handleStatusClick,
  handleDelete,
  handleOpenAccount,
  handleDownloadCookie,
  handleUploadCookie,
  handleDialogSubmit
} = useAccountDialog({ nameOptions, fetchNameOptions, fetchAccounts, getDefaultPlatform })

// 当前标签页与搜索关键词过滤后的账号
const visibleAccounts = computed(() => {
  const current = platformTabs.find(tab => tab.name === activeTab.value)
  const platform = current ? current.platform : ''
  const keyword = searchKeyword.value
  return accountStore.accounts.filter(account => {
    if (platform && account.platform !== platform) return false
    return !keyword || account.name.includes(keyword)
  })
})

// 失效账号（按 平台+名称 去重），用于顶部提示
const abnormalAccounts = computed(() => {
  const seen = new Set()
  return accountStore.accounts
    .filter(account => account.status === '异常')
    .filter(account => {
      const key = `${account.platform}/${account.name}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
})

// 失效账号提示文案
const abnormalDescription = computed(() => {
  const names = abnormalAccounts.value.map(account => `${account.platform} / ${account.name}`)
  return `请对以下账号点击“重新登录”完成扫码：${names.join('、')}`
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

.account-management {
  .account-tabs {
    background-color: var(--el-bg-color);
    border-radius: 4px;
    box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
    padding: 20px;
  }

  .account-search {
    display: flex;
    justify-content: space-between;
    margin-bottom: 10px;

    .el-input {
      width: 300px;
    }

    .action-buttons {
      display: flex;
      gap: 10px;

      .el-icon.is-loading {
        animation: rotate 1s linear infinite;
      }
    }
  }

  .status-alert {
    margin-bottom: 12px;
  }

  .account-list-container {
    .account-list {
      margin-bottom: 20px;
    }

    .empty-data {
      padding: 40px 0;
    }
  }
}
</style>
