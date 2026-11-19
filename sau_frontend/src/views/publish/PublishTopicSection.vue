<template>
  <!-- 标题输入 -->
  <div class="title-section">
    <h3>标题</h3>
    <el-input
      v-model="publish.form.title"
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
          v-for="(topic, index) in publish.form.selectedTopics"
          :key="index"
          closable
          @close="publish.removeTopic(index)"
          class="topic-tag"
        >
          #{{ topic }}
        </el-tag>
      </div>
      <el-button type="primary" plain @click="publish.openTopicDialog" class="select-topic-btn">
        添加话题
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { usePublishContext } from '@/composables/publish/publishContext'

const publish = usePublishContext()
</script>
