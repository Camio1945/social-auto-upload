<template>
  <div class="action-buttons">
    <el-button size="small" @click="publish.cancelPublish(tab)">取消</el-button>
    <el-button
      size="small"
      type="primary"
      @click="publish.confirmPublish(tab)"
      :loading="tab.publishing || false"
    >
      {{ tab.publishing ? '发布中...' : '发布' }}
    </el-button>
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
