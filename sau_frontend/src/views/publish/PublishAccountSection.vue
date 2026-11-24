<template>
  <div class="account-section">
    <div class="section-header">
      <h3>账号</h3>
      <el-button
        v-if="publish.userAccounts.length > 0"
        link
        type="primary"
        size="small"
        @click="toggleAllAccounts"
      >
        {{ allSelected ? '取消全选' : '全选' }}
      </el-button>
    </div>

    <!-- 选择名称 -->
    <div class="user-name-row">
      <span class="label">名称：</span>
      <el-radio-group v-model="publish.form.userName" class="user-name-radios">
        <el-radio
          v-for="item in publish.userNames"
          :key="item.id"
          :value="item.userName"
        >
          {{ item.userName }}
        </el-radio>
      </el-radio-group>
      <span v-if="publish.userNames.length === 0" class="platform-hint">
        暂无名称，请先在「名称管理」中添加
      </span>
    </div>

    <!-- 该名称下的账号，可多选 -->
    <div v-if="publish.form.userName" class="account-list">
      <el-empty
        v-if="publish.userAccounts.length === 0"
        description="该名称下暂无账号，请先在「账号管理」中添加"
        :image-size="80"
      />
      <el-checkbox-group v-else v-model="publish.form.accountIds" class="account-grid">
        <el-checkbox
          v-for="account in publish.userAccounts"
          :key="account.id"
          :label="account.id"
          class="account-checkbox"
        >
          <span class="platform-name">{{ account.platform }}</span>
          <el-tag size="small" :type="getStatusType(account.status)" effect="plain">
            {{ account.status }}
          </el-tag>
        </el-checkbox>
      </el-checkbox-group>
      <div v-if="publish.userAccounts.length > 0" class="account-tip">
        勾选需要发布的账号（每个账号对应一个平台），将同时发布到所选账号。
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { usePublishContext } from '@/composables/publish/publishContext'

const publish = usePublishContext()

// 该名称下的账号是否已全部选中
const allSelected = computed(() =>
  publish.userAccounts.length > 0 &&
  publish.userAccounts.every(account => publish.form.accountIds.includes(account.id))
)

// 一键全选 / 取消全选（每个账号对应一个平台）
const toggleAllAccounts = () => {
  publish.form.accountIds = allSelected.value
    ? []
    : publish.userAccounts.map(account => account.id)
}

// 状态标签颜色
const getStatusType = (status) => {
  if (status === '正常') return 'success'
  if (status === '验证中') return 'info'
  return 'danger'
}
</script>
