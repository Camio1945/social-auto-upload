import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAccountStore } from '@/stores/account'
import { accountApi } from '@/api/account'

// 平台类型编号到名称的映射
const platformMap = {
  3: '抖音',
  2: '视频号',
  1: '小红书',
  4: '快手'
}

const createAccountState = (accountStore) => {
  const accountDialogVisible = ref(false)
  const tempSelectedAccounts = ref([])
  const accountTab = ref(null)
  const accountLoading = ref(false)

  // 根据当前tab选择的平台获取可用账号列表
  const availableAccounts = computed(() => {
    const currentPlatform = accountTab.value ? platformMap[accountTab.value.selectedPlatform] : null
    if (!currentPlatform) return []
    return accountStore.accounts.filter(acc => acc.platform === currentPlatform)
  })

  return {
    accountDialogVisible,
    tempSelectedAccounts,
    accountTab,
    accountLoading,
    availableAccounts
  }
}

// 从后端获取账号列表（快速获取，不做cookie验证）
const createAccountsLoader = (accountStore, accountLoading) => async () => {
  try {
    const res = await accountApi.getAccounts()
    if (res.code === 200 && res.data) {
      accountStore.setAccounts(res.data)
    } else {
      ElMessage.error('获取账号列表失败')
    }
  } catch (error) {
    console.error('获取账号列表失败:', error)
    ElMessage.error('获取账号列表失败')
  } finally {
    accountLoading.value = false
  }
}

const createDialogActions = (state, accountStore) => {
  const loadAccounts = createAccountsLoader(accountStore, state.accountLoading)

  // 打开账号选择弹窗
  const openAccountDialog = async (tab) => {
    state.accountTab.value = tab
    state.tempSelectedAccounts.value = [...tab.selectedAccounts]
    state.accountLoading.value = true
    state.accountDialogVisible.value = true
    await loadAccounts()
  }

  // 确认账号选择
  const confirmAccountSelection = () => {
    if (state.accountTab.value) {
      state.accountTab.value.selectedAccounts = [...state.tempSelectedAccounts.value]
    }
    state.accountDialogVisible.value = false
    state.accountTab.value = null
    ElMessage.success('账号选择完成')
  }

  // 删除选中的账号
  const removeAccount = (tab, index) => {
    tab.selectedAccounts.splice(index, 1)
  }

  // 获取账号显示名称
  const getAccountDisplayName = (accountId) => {
    const account = accountStore.accounts.find(acc => acc.id === accountId)
    return account ? account.name : accountId
  }

  return { openAccountDialog, confirmAccountSelection, removeAccount, getAccountDisplayName }
}

export function usePublishAccounts() {
  const accountStore = useAccountStore()
  const state = createAccountState(accountStore)
  return { ...state, ...createDialogActions(state, accountStore) }
}
