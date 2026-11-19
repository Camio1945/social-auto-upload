<template>
  <el-dialog
    v-model="publish.accountDialogVisible"
    title="选择账号"
    width="600px"
    class="account-dialog"
  >
    <div class="account-dialog-content" v-loading="publish.accountLoading">
      <el-checkbox-group
        v-if="publish.availableAccounts.length > 0"
        v-model="publish.tempSelectedAccounts"
      >
        <div class="account-list">
          <el-checkbox
            v-for="account in publish.availableAccounts"
            :key="account.id"
            :label="account.id"
            class="account-item"
          >
            <div class="account-info">
              <span class="account-name">{{ account.name }}</span>
            </div>
          </el-checkbox>
        </div>
      </el-checkbox-group>
      <el-empty
        v-else-if="!publish.accountLoading"
        description="当前平台暂无可用账号，请先在「账号管理」中添加账号或切换发布平台"
        :image-size="80"
      />
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="publish.accountDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="publish.confirmAccountSelection">确定</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { usePublishContext } from '@/composables/publish/publishContext'

const publish = usePublishContext()
</script>
