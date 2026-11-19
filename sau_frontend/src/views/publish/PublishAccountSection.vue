<template>
  <div class="account-section">
    <h3>账号</h3>
    <div class="account-display">
      <div class="selected-accounts">
        <el-tag
          v-for="(account, index) in tab.selectedAccounts"
          :key="index"
          closable
          @close="publish.removeAccount(tab, index)"
          class="account-tag"
        >
          {{ publish.getAccountDisplayName(account) }}
        </el-tag>
      </div>
      <el-button
        type="primary"
        plain
        @click="publish.openAccountDialog(tab)"
        class="select-account-btn"
      >
        选择账号
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { usePublishContext } from '@/composables/publish/publishContext'

defineProps({
  tab: {
    type: Object,
    required: true
  }
})

const publish = usePublishContext()
</script>
