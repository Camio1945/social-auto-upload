<template>
  <div class="publish-center">
    <!-- Tab管理区域 -->
    <PublishTabList />

    <!-- 内容区域 -->
    <div class="publish-content">
      <div class="tab-content-wrapper">
        <PublishTabPanel
          v-for="tab in publish.tabs"
          :key="tab.name"
          v-show="publish.activeTab === tab.name"
          :tab="tab"
        />
      </div>
    </div>

    <!-- 全局弹窗 -->
    <UploadOptionsDialog />
    <LocalUploadDialog />
    <MaterialSelectDialog />
    <AccountSelectDialog />
    <TopicSelectDialog />
    <BatchPublishDialog />
  </div>
</template>

<script setup>
import { provide } from 'vue'
import PublishTabList from './publish/PublishTabList.vue'
import PublishTabPanel from './publish/PublishTabPanel.vue'
import UploadOptionsDialog from './publish/UploadOptionsDialog.vue'
import LocalUploadDialog from './publish/LocalUploadDialog.vue'
import MaterialSelectDialog from './publish/MaterialSelectDialog.vue'
import AccountSelectDialog from './publish/AccountSelectDialog.vue'
import TopicSelectDialog from './publish/TopicSelectDialog.vue'
import BatchPublishDialog from './publish/BatchPublishDialog.vue'
import { usePublishCenter } from '@/composables/publish/usePublishCenter'
import { PUBLISH_KEY } from '@/composables/publish/publishContext'

// 创建共享状态并注入给子组件
const publish = usePublishCenter()
provide(PUBLISH_KEY, publish)
</script>

<style lang="scss" src="./publish/publish-center.scss"></style>
