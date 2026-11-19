import { ElMessage } from 'element-plus'
import { http } from '@/utils/request'
import { getPlatformName, resetFormAfterPublish } from './usePublishForm'

// 校验表单数据，返回错误提示；无错误时返回 null
const validateForm = (form, selectedAccounts) => {
  if (form.fileList.length === 0) return '请先上传视频文件'
  if (!form.title.trim()) return '请输入标题'
  if (selectedAccounts.length === 0) return '请至少选择一个账号'
  return null
}

// 按平台对账号分组，每个平台调用一次发布接口
const groupByPlatform = (accounts) => {
  const groups = new Map()
  accounts.forEach(account => {
    if (!groups.has(account.type)) groups.set(account.type, [])
    groups.get(account.type).push(account)
  })
  return groups
}

// 构造单个平台的发布数据
const buildPayload = (form, platformType, accounts) => ({
  type: platformType,
  title: form.title.trim(),
  tags: form.selectedTopics, // 不带#号的话题列表
  fileList: form.fileList.map(file => file.path),
  accountList: accounts.map(account => account.filePath),
  enableTimer: form.scheduleEnabled ? 1 : 0,
  videosPerDay: form.scheduleEnabled ? form.videosPerDay || 1 : 1,
  dailyTimes: form.scheduleEnabled ? form.dailyTimes || ['10:00'] : ['10:00'],
  startDays: form.scheduleEnabled ? form.startDays || 0 : 0,
  category: form.isOriginal ? 1 : 0, // 1表示原创，0表示非原创
  // 平台专属字段只在对应平台发送
  productLink: platformType === 3 ? form.productLink.trim() : '',
  productTitle: platformType === 3 ? form.productTitle.trim() : '',
  isDraft: platformType === 2 ? form.isDraft : false
})

// 依次发布到各个平台，返回失败的平台列表（含编号与名称）
const publishPlatforms = async (form, groups) => {
  const failures = []
  let index = 0
  for (const [platformType, accounts] of groups) {
    index++
    form.publishStatus = {
      message: `正在发布：${getPlatformName(platformType)}（${index}/${groups.size}）...`,
      type: 'info'
    }
    try {
      await http.post('/postVideo', buildPayload(form, platformType, accounts))
    } catch (error) {
      console.error(`发布到${getPlatformName(platformType)}失败:`, error)
      failures.push({ type: platformType, name: getPlatformName(platformType) })
    }
  }
  return failures
}

// 取消发布（仅提示，实际任务由后端处理）
const createCancelPublish = () => () => {
  ElMessage.info('已取消发布')
}

export function usePublishSubmit(form, selectedAccounts) {
  // 确认发布：同一视频、同一标题、同一时间发布到所有勾选的账号
  const confirmPublish = async () => {
    if (form.publishing) return

    const invalidMessage = validateForm(form, selectedAccounts.value)
    if (invalidMessage) {
      ElMessage.error(invalidMessage)
      form.publishStatus = { message: invalidMessage, type: 'error' }
      return
    }

    form.publishing = true
    try {
      const groups = groupByPlatform(selectedAccounts.value)
      const failures = await publishPlatforms(form, groups)
      if (failures.length === 0) {
        form.publishStatus = { message: '发布成功', type: 'success' }
        resetFormAfterPublish(form)
      } else {
        // 只保留失败平台的账号，避免重试时向已成功平台重复发布
        const failedTypes = new Set(failures.map(item => item.type))
        form.accountIds = selectedAccounts.value
          .filter(account => failedTypes.has(account.type))
          .map(account => account.id)
        form.publishStatus = {
          message: `发布完成，以下平台失败：${failures.map(item => item.name).join('、')}（已保留失败平台的账号，可重新发布）`,
          type: 'error'
        }
      }
    } finally {
      form.publishing = false
    }
  }

  return { confirmPublish, cancelPublish: createCancelPublish() }
}
