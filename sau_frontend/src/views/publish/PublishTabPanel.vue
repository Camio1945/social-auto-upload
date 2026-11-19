<template>
  <div class="tab-content">
    <div v-if="tab.publishStatus" class="publish-status">
      <el-alert
        :title="tab.publishStatus.message"
        :type="tab.publishStatus.type"
        :closable="false"
        show-icon
      />
    </div>
    <PublishVideoSection :tab="tab" />
    <PublishAccountSection :tab="tab" />
    <PublishPlatformSection :tab="tab" />
    <PublishTopicSection :tab="tab" />
    <PublishScheduleSection :tab="tab" />
    <PublishActions :tab="tab" />
  </div>
</template>

<script setup>
import PublishVideoSection from './PublishVideoSection.vue'
import PublishAccountSection from './PublishAccountSection.vue'
import PublishPlatformSection from './PublishPlatformSection.vue'
import PublishTopicSection from './PublishTopicSection.vue'
import PublishScheduleSection from './PublishScheduleSection.vue'
import PublishActions from './PublishActions.vue'

defineProps({
  tab: {
    type: Object,
    required: true
  }
})
</script>
