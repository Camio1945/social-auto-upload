<template>
  <!-- 标题输入 -->
  <div class="title-section">
    <h3>标题</h3>
    <el-input
      v-model="tab.title"
      type="textarea"
      :rows="3"
      placeholder="请输入标题"
      maxlength="100"
      show-word-limit
      class="title-input"
    />
  </div>

  <!-- 话题输入 -->
  <div class="topic-section">
    <h3>话题</h3>
    <div class="topic-display">
      <div class="selected-topics">
        <el-tag
          v-for="(topic, index) in tab.selectedTopics"
          :key="index"
          closable
          @close="publish.removeTopic(tab, index)"
          class="topic-tag"
        >
          #{{ topic }}
        </el-tag>
      </div>
      <el-button
        type="primary"
        plain
        @click="publish.openTopicDialog(tab)"
        class="select-topic-btn"
      >
        添加话题
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
