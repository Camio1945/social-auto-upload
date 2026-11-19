<template>
  <div class="publish-center">
    <!-- 内容区域：单页面发布，不再使用多 tab -->
    <div class="publish-content">
      <div class="panel-wrapper">
        <PublishPanel />
      </div>
    </div>

    <!-- 全局弹窗 -->
    <UploadOptionsDialog />
    <LocalUploadDialog />
    <MaterialSelectDialog />
    <TopicSelectDialog />
  </div>
</template>

<script setup>
import { onMounted, provide } from 'vue'
import PublishPanel from './publish/PublishPanel.vue'
import UploadOptionsDialog from './publish/UploadOptionsDialog.vue'
import LocalUploadDialog from './publish/LocalUploadDialog.vue'
import MaterialSelectDialog from './publish/MaterialSelectDialog.vue'
import TopicSelectDialog from './publish/TopicSelectDialog.vue'
import { usePublishCenter } from '@/composables/publish/usePublishCenter'
import { PUBLISH_KEY } from '@/composables/publish/publishContext'

// 创建共享状态并注入给子组件
const publish = usePublishCenter()
provide(PUBLISH_KEY, publish)

// 进入页面时加载名称与账号列表
onMounted(() => {
  publish.initialize()
})
</script>

<style lang="scss" src="./publish/publish-center.scss"></style>
