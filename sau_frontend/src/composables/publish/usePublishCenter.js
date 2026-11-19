import { reactive } from 'vue'
import { usePublishTabs } from './usePublishTabs'
import { usePublishUpload } from './usePublishUpload'
import { usePublishAccounts } from './usePublishAccounts'
import { usePublishTopics } from './usePublishTopics'
import { usePublishSubmit } from './usePublishSubmit'
import { useBatchPublish } from './useBatchPublish'

// 汇总发布中心的所有状态与方法，供页面与子组件共享
export function usePublishCenter() {
  const tabsState = usePublishTabs()
  const upload = usePublishUpload()
  const accounts = usePublishAccounts()
  const topics = usePublishTopics()
  const submit = usePublishSubmit()
  const batch = useBatchPublish(tabsState.tabs, submit.confirmPublish)

  return reactive({
    ...tabsState,
    ...upload,
    ...accounts,
    ...topics,
    ...submit,
    ...batch
  })
}
