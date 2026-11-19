import { ref } from 'vue'
import { ElMessage } from 'element-plus'

// 推荐话题列表
const recommendedTopics = [
  '游戏', '电影', '音乐', '美食', '旅行', '文化',
  '科技', '生活', '娱乐', '体育', '教育', '艺术',
  '健康', '时尚', '美妆', '摄影', '宠物', '汽车'
]

const createTopicState = () => ({
  topicDialogVisible: ref(false),
  topicTab: ref(null),
  customTopic: ref('')
})

const createTopicActions = (state) => {
  // 添加自定义话题
  const addCustomTopic = () => {
    const content = state.customTopic.value.trim()
    if (!content) {
      ElMessage.warning('请输入话题内容')
      return
    }
    if (state.topicTab.value && state.topicTab.value.selectedTopics.includes(content)) {
      ElMessage.warning('话题已存在')
      return
    }
    if (state.topicTab.value) {
      state.topicTab.value.selectedTopics.push(content)
      state.customTopic.value = ''
      ElMessage.success('话题添加成功')
    }
  }

  // 切换推荐话题
  const toggleRecommendedTopic = (topic) => {
    if (!state.topicTab.value) return
    const topics = state.topicTab.value.selectedTopics
    const index = topics.indexOf(topic)
    if (index > -1) {
      topics.splice(index, 1)
    } else {
      topics.push(topic)
    }
  }

  // 删除话题
  const removeTopic = (tab, index) => {
    tab.selectedTopics.splice(index, 1)
  }

  // 确认添加话题
  const confirmTopicSelection = () => {
    state.topicDialogVisible.value = false
    state.customTopic.value = ''
    state.topicTab.value = null
    ElMessage.success('添加话题完成')
  }

  return { addCustomTopic, toggleRecommendedTopic, removeTopic, confirmTopicSelection }
}

export function usePublishTopics() {
  const state = createTopicState()

  // 打开添加话题弹窗
  const openTopicDialog = (tab) => {
    state.topicTab.value = tab
    state.topicDialogVisible.value = true
  }

  return { recommendedTopics, ...state, openTopicDialog, ...createTopicActions(state) }
}
