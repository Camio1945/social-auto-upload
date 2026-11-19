import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useAccountStore } from '@/stores/account'
import { accountApi } from '@/api/account'
import { userNameApi } from '@/api/userName'

// 从后端获取名称列表
const fetchUserNames = async (userNames) => {
  try {
    const res = await userNameApi.getUserNames()
    if (res.code === 200 && res.data) {
      userNames.value = res.data
    }
  } catch (error) {
    console.error('获取名称列表失败:', error)
    ElMessage.error('获取名称列表失败')
  }
}

// 从后端获取账号列表（快速获取，不做cookie验证）
const fetchAccounts = async (accountStore) => {
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
  }
}

export function usePublishAccounts(form) {
  const accountStore = useAccountStore()
  const userNames = ref([])
  const accountLoading = ref(false)

  // 当前名称下已存在的账号
  const userAccounts = computed(() =>
    accountStore.accounts.filter(account => account.name === form.userName)
  )

  // 已勾选的账号
  const selectedAccounts = computed(() =>
    userAccounts.value.filter(account => form.accountIds.includes(account.id))
  )

  // 已选账号对应的平台编号（自动决定要发布到哪些平台）
  const selectedPlatforms = computed(() =>
    [...new Set(selectedAccounts.value.map(account => account.type))]
  )

  // 初始化：加载名称与账号
  const initialize = async () => {
    accountLoading.value = true
    try {
      await Promise.all([fetchUserNames(userNames), fetchAccounts(accountStore)])
    } finally {
      accountLoading.value = false
    }
  }

  // 切换名称时清空已选账号
  watch(() => form.userName, () => {
    form.accountIds = []
  })

  return {
    userNames,
    accountLoading,
    userAccounts,
    selectedAccounts,
    selectedPlatforms,
    initialize
  }
}
