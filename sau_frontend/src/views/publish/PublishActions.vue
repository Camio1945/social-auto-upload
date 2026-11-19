<template>
  <div class="action-buttons">
    <el-button size="small" @click="publish.cancelPublish">取消</el-button>
    <el-button
      size="small"
      type="primary"
      @click="publish.confirmPublish"
      :loading="publish.form.publishing || false"
    >
      {{ publish.form.publishing ? '发布中...' : '发布' }}
    </el-button>
  </div>
</template>

<script setup>
import { usePublishContext } from '@/composables/publish/publishContext'

const publish = usePublishContext()
</script>
