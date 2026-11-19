<template>
  <el-dialog
    v-model="publish.topicDialogVisible"
    title="添加话题"
    width="600px"
    class="topic-dialog"
  >
    <div class="topic-dialog-content">
      <!-- 自定义话题输入 -->
      <div class="custom-topic-input">
        <el-input v-model="publish.customTopic" placeholder="输入自定义话题" class="custom-input">
          <template #prepend>#</template>
        </el-input>
        <el-button type="primary" @click="publish.addCustomTopic">添加</el-button>
      </div>

      <!-- 推荐话题 -->
      <div class="recommended-topics">
        <h4>推荐话题</h4>
        <div class="topic-grid">
          <el-button
            v-for="topic in publish.recommendedTopics"
            :key="topic"
            :type="isTopicSelected(topic) ? 'primary' : 'default'"
            @click="publish.toggleRecommendedTopic(topic)"
            class="topic-btn"
          >
            {{ topic }}
          </el-button>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="publish.topicDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="publish.confirmTopicSelection">确定</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { usePublishContext } from '@/composables/publish/publishContext'

const publish = usePublishContext()

const isTopicSelected = (topic) => {
  return Boolean(publish.topicTab?.selectedTopics?.includes(topic))
}
</script>
