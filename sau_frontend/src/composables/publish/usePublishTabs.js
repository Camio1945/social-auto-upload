import { reactive, ref } from 'vue'

// 平台列表 - 对应后端 type 字段
export const platforms = [
  { key: 3, name: '抖音' },
  { key: 4, name: '快手' },
  { key: 2, name: '视频号' },
  { key: 1, name: '小红书' }
]

const defaultTabInit = {
  name: 'tab1',
  label: '发布1',
  fileList: [], // 后端返回的文件名列表
  displayFileList: [], // 用于显示的文件列表
  selectedAccounts: [], // 选中的账号ID列表
  selectedPlatform: 1, // 选中的平台（单选）
  title: '',
  productLink: '', // 商品链接
  productTitle: '', // 商品名称
  selectedTopics: [], // 话题列表（不带#号）
  scheduleEnabled: false, // 定时发布开关
  videosPerDay: 1, // 每天发布视频数量
  dailyTimes: ['10:00'], // 每天发布时间点列表
  startDays: 0, // 从今天开始计算的发布天数，0表示明天，1表示后天
  publishStatus: null, // 发布状态，包含message和type
  publishing: false, // 发布状态，用于控制按钮loading效果
  isDraft: false, // 是否保存为草稿，仅视频号平台可见
  isOriginal: false // 是否标记为原创
}

// 创建一个全新的 tab，使用深拷贝避免多个 tab 共享引用
const makeNewTab = () => {
  try {
    return typeof structuredClone === 'function'
      ? structuredClone(defaultTabInit)
      : JSON.parse(JSON.stringify(defaultTabInit))
  } catch (error) {
    return JSON.parse(JSON.stringify(defaultTabInit))
  }
}

export function usePublishTabs() {
  // 当前激活的tab
  const activeTab = ref('tab1')

  // tab页数据 - 默认只有一个tab
  const tabs = reactive([makeNewTab()])

  // tab计数器
  let tabCounter = 1

  // 添加新tab
  const addTab = () => {
    tabCounter++
    const newTab = makeNewTab()
    newTab.name = `tab${tabCounter}`
    newTab.label = `发布${tabCounter}`
    tabs.push(newTab)
    activeTab.value = newTab.name
  }

  // 删除tab
  const removeTab = (tabName) => {
    const index = tabs.findIndex(tab => tab.name === tabName)
    if (index === -1) return
    tabs.splice(index, 1)
    // 如果删除的是当前激活的tab，切换到第一个tab
    if (activeTab.value === tabName && tabs.length > 0) {
      activeTab.value = tabs[0].name
    }
  }

  return { tabs, activeTab, addTab, removeTab }
}
