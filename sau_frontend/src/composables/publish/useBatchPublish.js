import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const createBatchState = () => {
  const batchPublishing = ref(false)
  const batchPublishDialogVisible = ref(false)
  const currentPublishingTab = ref(null)
  const publishProgress = ref(0)
  const publishResults = ref([])
  const isCancelled = ref(false)

  // 取消批量发布
  const cancelBatchPublish = () => {
    isCancelled.value = true
    ElMessage.info('正在取消发布...')
  }

  return {
    batchPublishing,
    batchPublishDialogVisible,
    currentPublishingTab,
    publishProgress,
    publishResults,
    isCancelled,
    cancelBatchPublish
  }
}

// 发布单个tab，返回结果记录
const publishTabWithResult = async (tab, confirmPublish) => {
  try {
    await confirmPublish(tab)
    return { label: tab.label, status: 'success', message: '发布成功' }
  } catch (error) {
    return { label: tab.label, status: 'error', message: error.message }
  }
}

// 根据发布结果显示提示信息
const notifyBatchResult = (state) => {
  const successCount = state.publishResults.value.filter(r => r.status === 'success').length
  const failCount = state.publishResults.value.filter(r => r.status === 'error').length
  const cancelCount = state.publishResults.value.filter(r => r.status === 'cancelled').length

  if (state.isCancelled.value) {
    ElMessage.warning(`发布已取消：${successCount}个成功，${failCount}个失败，${cancelCount}个未执行`)
    return
  }
  if (failCount > 0) {
    ElMessage.error(`发布完成：${successCount}个成功，${failCount}个失败`)
    return
  }
  ElMessage.success('所有Tab发布成功')
  setTimeout(() => {
    state.batchPublishDialogVisible.value = false
  }, 1000)
}

const createBatchRunner = (state, tabs, confirmPublish) => async () => {
  if (state.batchPublishing.value) return

  state.batchPublishing.value = true
  state.currentPublishingTab.value = null
  state.publishProgress.value = 0
  state.publishResults.value = []
  state.isCancelled.value = false
  state.batchPublishDialogVisible.value = true

  try {
    for (let i = 0; i < tabs.length; i++) {
      const tab = tabs[i]
      if (state.isCancelled.value) {
        state.publishResults.value.push({ label: tab.label, status: 'cancelled', message: '已取消' })
        continue
      }
      state.currentPublishingTab.value = tab
      state.publishProgress.value = Math.floor((i / tabs.length) * 100)
      state.publishResults.value.push(await publishTabWithResult(tab, confirmPublish))
    }
    state.publishProgress.value = 100
    notifyBatchResult(state)
  } catch (error) {
    console.error('批量发布出错:', error)
    ElMessage.error('批量发布出错，请重试')
  } finally {
    state.batchPublishing.value = false
    state.isCancelled.value = false
  }
}

export function useBatchPublish(tabs, confirmPublish) {
  const state = createBatchState()
  return { ...state, batchPublish: createBatchRunner(state, tabs, confirmPublish) }
}
