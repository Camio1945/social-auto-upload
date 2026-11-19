import { ElMessage } from 'element-plus'
import { useAccountStore } from '@/stores/account'
import { http } from '@/utils/request'

// 校验tab数据，返回错误提示；无错误时返回null
const ensurePublishable = (tab) => {
  if (tab.fileList.length === 0) return '请先上传视频文件'
  if (!tab.title.trim()) return '请输入标题'
  if (!tab.selectedPlatform) return '请选择发布平台'
  if (tab.selectedAccounts.length === 0) return '请选择发布账号'
  return null
}

// 发布成功后清空当前tab的数据
const resetTabAfterPublish = (tab) => {
  tab.fileList = []
  tab.displayFileList = []
  tab.title = ''
  tab.selectedTopics = []
  tab.selectedAccounts = []
  tab.scheduleEnabled = false
}

// 账号ID转换为后端需要的cookie文件路径
const createAccountPathResolver = (accountStore) => (accountId) => {
  const account = accountStore.accounts.find(acc => acc.id === accountId)
  return account ? account.filePath : accountId
}

// 构造发布数据，符合后端API格式
const createPayloadBuilder = (accountStore) => {
  const toAccountFilePath = createAccountPathResolver(accountStore)
  return (tab) => ({
    type: tab.selectedPlatform,
    title: tab.title,
    tags: tab.selectedTopics, // 不带#号的话题列表
    fileList: tab.fileList.map(file => file.path), // 只发送文件路径
    accountList: tab.selectedAccounts.map(toAccountFilePath),
    enableTimer: tab.scheduleEnabled ? 1 : 0,
    videosPerDay: tab.scheduleEnabled ? tab.videosPerDay || 1 : 1,
    dailyTimes: tab.scheduleEnabled ? tab.dailyTimes || ['10:00'] : ['10:00'],
    startDays: tab.scheduleEnabled ? tab.startDays || 0 : 0,
    category: tab.isOriginal ? 1 : 0, // 1表示原创，0表示非原创
    productLink: tab.productLink.trim() || '',
    productTitle: tab.productTitle.trim() || '',
    isDraft: tab.isDraft
  })
}

// 确认发布
const createConfirmPublish = (accountStore) => {
  const buildPublishData = createPayloadBuilder(accountStore)
  return async (tab) => {
    // 防止重复点击
    if (tab.publishing) {
      throw new Error('正在发布中，请稍候...')
    }
    tab.publishing = true

    const invalidMessage = ensurePublishable(tab)
    if (invalidMessage) {
      ElMessage.error(invalidMessage)
      tab.publishing = false
      throw new Error(invalidMessage)
    }

    try {
      await http.post('/postVideo', buildPublishData(tab))
      tab.publishStatus = { message: '发布成功', type: 'success' }
      resetTabAfterPublish(tab)
    } catch (error) {
      console.error('发布错误:', error)
      tab.publishStatus = {
        message: `发布失败：${error.message || '请检查网络连接'}`,
        type: 'error'
      }
      throw error
    } finally {
      tab.publishing = false
    }
  }
}

// 取消发布
const cancelPublish = () => {
  ElMessage.info('已取消发布')
}

export function usePublishSubmit() {
  const accountStore = useAccountStore()
  return { confirmPublish: createConfirmPublish(accountStore), cancelPublish }
}
