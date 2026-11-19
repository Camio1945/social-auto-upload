import { ref } from 'vue'
import { ElMessage } from 'element-plus'

// 推荐话题列表
const recommendedTopics = [
  '游戏', '电影', '音乐', '美食', '旅行', '文化',
  '科技', '生活', '娱乐', '体育', '教育', '艺术',
  '健康', '时尚', '美妆', '摄影', '宠物', '汽车'
]

// 创建话题相关的操作
const createTopicActions = (form, topicDialogVisible, customTopic) => {
  const openTopicDialog = () => {
    topicDialogVisible.value = true
  }

  const addCustomTopic = () => {
    const content = customTopic.value.trim()
    if (!content) {
      ElMessage.warning('请输入话题内容')
      return
    }
    if (form.selectedTopics.includes(content)) {
      ElMessage.warning('话题已存在')
      return
    }
    form.selectedTopics.push(content)
    customTopic.value = ''
    ElMessage.success('话题添加成功')
  }

  const toggleRecommendedTopic = (topic) => {
    const index = form.selectedTopics.indexOf(topic)
    if (index > -1) {
      form.selectedTopics.splice(index, 1)
    } else {
      form.selectedTopics.push(topic)
    }
  }

  const removeTopic = (index) => {
    form.selectedTopics.splice(index, 1)
  }

  const confirmTopicSelection = () => {
    topicDialogVisible.value = false
    customTopic.value = ''
    ElMessage.success('添加话题完成')
  }

  return { openTopicDialog, addCustomTopic, toggleRecommendedTopic, removeTopic, confirmTopicSelection }
}

export function usePublishTopics(form) {
  const topicDialogVisible = ref(false)
  const customTopic = ref('')
  const actions = createTopicActions(form, topicDialogVisible, customTopic)
  return { recommendedTopics, topicDialogVisible, customTopic, ...actions }
}
