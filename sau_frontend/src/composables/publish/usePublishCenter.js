import { reactive } from 'vue'
import { createPublishForm } from './usePublishForm'
import { usePublishUpload } from './usePublishUpload'
import { usePublishAccounts } from './usePublishAccounts'
import { usePublishTopics } from './usePublishTopics'
import { usePublishSubmit } from './usePublishSubmit'

// 汇总发布中心的所有状态与方法，供页面与子组件共享
export function usePublishCenter() {
  const form = createPublishForm()
  const upload = usePublishUpload(form)
  const accounts = usePublishAccounts(form)
  const topics = usePublishTopics(form)
  const submit = usePublishSubmit(form, accounts.selectedAccounts)

  return reactive({
    form,
    ...upload,
    ...accounts,
    ...topics,
    ...submit
  })
}
