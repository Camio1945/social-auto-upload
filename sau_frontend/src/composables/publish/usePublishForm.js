import { reactive } from 'vue'

// 平台列表 - 对应后端 type 字段
export const platforms = [
  { key: 3, name: '抖音' },
  { key: 4, name: '快手' },
  { key: 2, name: '视频号' },
  { key: 1, name: '小红书' }
]

// 根据平台编号获取平台名称
export const getPlatformName = (type) => {
  const platform = platforms.find(item => item.key === type)
  return platform ? platform.name : String(type)
}

// 发布中心的表单默认值（单页面，无多 tab）
const createDefaultForm = () => ({
  userName: '', // 选中的名称
  accountIds: [], // 选中的账号ID列表（同一名称下的多个平台账号）
  fileList: [], // 后端返回的文件列表
  displayFileList: [], // 用于显示的文件列表
  title: '',
  selectedTopics: [], // 话题列表（不带#号）
  scheduleEnabled: false, // 定时发布开关
  videosPerDay: 1, // 每天发布视频数量
  dailyTimes: ['10:00'], // 每天发布时间点列表
  startDays: 0, // 发布开始天数：0 明天，1 后天
  isOriginal: false, // 是否声明原创
  isDraft: false, // 视频号是否仅保存草稿
  productLink: '', // 抖音商品链接
  productTitle: '', // 抖音商品名称
  publishStatus: null, // 发布状态，包含 message 和 type
  publishing: false // 是否正在发布
})

// 发布页选择状态的本地存储键（名称、账号、原创声明）
const PUBLISH_STATE_KEY = 'publishCenterSelection'

// 保存名称、账号与原创声明到本地存储
export const savePublishState = (form) => {
  try {
    localStorage.setItem(PUBLISH_STATE_KEY, JSON.stringify({
      userName: form.userName,
      accountIds: form.accountIds,
      isOriginal: form.isOriginal
    }))
  } catch (error) {
    console.error('保存发布页选择状态失败:', error)
  }
}

// 从本地存储恢复名称、账号与原创声明
export const applyPersistedPublishState = (form) => {
  try {
    const raw = localStorage.getItem(PUBLISH_STATE_KEY)
    if (!raw) return
    const state = JSON.parse(raw)
    if (typeof state.userName === 'string') form.userName = state.userName
    if (Array.isArray(state.accountIds)) form.accountIds = state.accountIds
    if (typeof state.isOriginal === 'boolean') form.isOriginal = state.isOriginal
  } catch (error) {
    console.error('读取发布页选择状态失败:', error)
  }
}

export const createPublishForm = () => reactive(createDefaultForm())

// 发布成功后重置内容，保留名称与已选账号方便连续发布
export const resetFormAfterPublish = (form) => {
  form.fileList = []
  form.displayFileList = []
  form.title = ''
  form.selectedTopics = []
  form.scheduleEnabled = false
}
