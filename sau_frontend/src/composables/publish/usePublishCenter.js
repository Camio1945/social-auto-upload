import { reactive, watch } from 'vue'
import { createPublishForm, applyPersistedPublishState, savePublishState } from './usePublishForm'
import { usePublishUpload } from './usePublishUpload'
import { usePublishAccounts } from './usePublishAccounts'
import { usePublishTopics } from './usePublishTopics'
import { usePublishSubmit } from './usePublishSubmit'

// 恢复本地状态后，校验名称与账号是否仍然存在
const pruneInvalidSelection = (form, accounts) => {
  const names = accounts.userNames.value
  if (form.userName && !names.some(item => item.userName === form.userName)) {
    form.userName = ''
    form.accountIds = []
    return
  }
  form.accountIds = form.accountIds.filter(id =>
    accounts.userAccounts.value.some(account => account.id === id)
  )
}

// 汇总发布中心的所有状态与方法，供页面与子组件共享
export function usePublishCenter() {
  const form = createPublishForm()
  // 先恢复上次的选择，再创建账号相关的 watch，避免刚恢复就被清空
  applyPersistedPublishState(form)

  const upload = usePublishUpload(form)
  const accounts = usePublishAccounts(form)
  const topics = usePublishTopics(form)
  const submit = usePublishSubmit(form, accounts.selectedAccounts)

  // 初始化：加载名称与账号，并清理已失效的本地选择
  const initialize = async () => {
    await accounts.initialize()
    pruneInvalidSelection(form, accounts)
  }

  // 名称、账号、原创声明变化时持久化到本地存储
  watch(
    () => [form.userName, form.accountIds, form.isOriginal],
    () => savePublishState(form),
    { deep: true }
  )

  return reactive({
    form,
    ...upload,
    ...accounts,
    ...topics,
    ...submit,
    initialize
  })
}
