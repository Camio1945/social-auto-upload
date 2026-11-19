<template>
  <div class="publish-panel">
    <div v-if="publish.form.publishStatus" class="publish-status">
      <el-alert
        :title="publish.form.publishStatus.message"
        :type="publish.form.publishStatus.type"
        :closable="false"
        show-icon
      />
    </div>
    <PublishVideoSection />
    <PublishAccountSection />
    <PublishPlatformSection />
    <PublishTopicSection />
    <PublishScheduleSection />
    <PublishActions />
  </div>
</template>

<script setup>
import PublishVideoSection from './PublishVideoSection.vue'
import PublishAccountSection from './PublishAccountSection.vue'
import PublishPlatformSection from './PublishPlatformSection.vue'
import PublishTopicSection from './PublishTopicSection.vue'
import PublishScheduleSection from './PublishScheduleSection.vue'
import PublishActions from './PublishActions.vue'
import { usePublishContext } from '@/composables/publish/publishContext'

const publish = usePublishContext()
</script>
