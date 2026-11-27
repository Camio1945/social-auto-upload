import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { accountApi } from '@/api/account'
import { userNameApi } from '@/api/userName'
import { useAccountStore } from '@/stores/account'
import { useAppStore } from '@/stores/app'

// 上次自动校验账号状态的日期（本地存储，按天去重）
const LAST_CHECK_DATE_KEY = 'lastAccountCheckDate'
// 校验结果的新鲜度阈值：超过该时长，打开页面时重新校验
const STALE_MS = 6 * 60 * 60 * 1000

// 获取本地日期字符串（YYYY-MM-DD）
const getTodayDate = () => {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

// 判断今天是否还未校验过账号状态
const shouldAutoCheckToday = () => {
  return localStorage.getItem(LAST_CHECK_DATE_KEY) !== getTodayDate()
}

// 记录今天已完成校验
const markCheckedToday = () => {
  localStorage.setItem(LAST_CHECK_DATE_KEY, getTodayDate())
}

// 解析后端返回的 lastCheckedAt（YYYY-MM-DD HH:mm:ss）
const parseCheckedAt = (value) => {
  if (!value) return null
  const time = new Date(String(value).replace(' ', 'T')).getTime()
  return Number.isNaN(time) ? null : time
}

// 只要有一条记录从未校验或已过期，就需要重新校验
const isCheckStale = (accounts) => {
  const now = Date.now()
  return accounts.some((account) => {
    const checkedAt = parseCheckedAt(account[5])
    return checkedAt === null || now - checkedAt > STALE_MS
  })
}

// 创建名称列表状态
const createNameOptions = () => {
  const nameOptions = ref([])

  const fetchNameOptions = async () => {
    try {
      const res = await userNameApi.getUserNames()
      if (res.code === 200 && res.data) {
        nameOptions.value = res.data
      }
    } catch (error) {
      console.error('获取名称列表失败:', error)
    }
  }

  return { nameOptions, fetchNameOptions }
}

// 获取账号数据（快速，不验证），返回后端原始行数据
const fetchAccountsQuick = async (accountStore) => {
  try {
    const res = await accountApi.getAccounts()
    if (res.code === 200 && res.data) {
      accountStore.setAccounts(res.data)
      return res.data
    }
  } catch (error) {
    console.error('快速获取账号数据失败:', error)
  }
  return []
}

// 把账号状态临时标记为「验证中」
const markAccountsPending = (accountStore, accounts) => {
  if (!accounts.length) return
  const pending = accounts.map((account) => {
    const copy = [...account]
    copy[4] = -1
    return copy
  })
  accountStore.setAccounts(pending)
}

// 获取账号数据（带验证）；silent 为 true 时不弹成功提示
const fetchValidAccounts = async (accountStore, appStore, silent = false) => {
  if (appStore.isAccountRefreshing) return
  appStore.setAccountRefreshing(true)

  try {
    const res = await accountApi.getValidAccounts()
    if (res.code === 200 && res.data) {
      accountStore.setAccounts(res.data)
      markCheckedToday()
      if (!silent) ElMessage.success('账号数据获取成功')
      if (appStore.isFirstTimeAccountManagement) {
        appStore.setAccountManagementVisited()
      }
    } else if (!silent) {
      ElMessage.error('获取账号数据失败')
    }
  } catch (error) {
    console.error('获取账号数据失败:', error)
    if (!silent) ElMessage.error('获取账号数据失败')
  } finally {
    appStore.setAccountRefreshing(false)
  }
}

export function useAccountStatus() {
  const accountStore = useAccountStore()
  const appStore = useAppStore()
  const { nameOptions, fetchNameOptions } = createNameOptions()

  const fetchAccounts = () => fetchValidAccounts(accountStore, appStore)
  // 不带校验的快速刷新：保活等后台动作改了状态后同步到列表
  const refreshAccountsQuick = () => fetchAccountsQuick(accountStore)

  onMounted(async () => {
    fetchNameOptions()

    // 先展示上次的校验结果，再按需在后台重新校验
    const accounts = await fetchAccountsQuick(accountStore)
    if (!shouldAutoCheckToday() && !isCheckStale(accounts)) return

    markAccountsPending(accountStore, accounts)
    await fetchValidAccounts(accountStore, appStore, true)
  })

  return {
    accountStore,
    appStore,
    nameOptions,
    fetchNameOptions,
    fetchAccounts,
    refreshAccountsQuick
  }
}
