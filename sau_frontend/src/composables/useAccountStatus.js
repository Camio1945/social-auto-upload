import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { accountApi } from '@/api/account'
import { userNameApi } from '@/api/userName'
import { useAccountStore } from '@/stores/account'
import { useAppStore } from '@/stores/app'

// 上次自动校验账号状态的日期（本地存储，按天去重）
const LAST_CHECK_DATE_KEY = 'lastAccountCheckDate'

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

// 获取账号数据（快速，不验证）
// showPending 为 true 时把状态显示为"验证中"（即将在后台校验）
const fetchAccountsQuick = async (accountStore, showPending) => {
  try {
    const res = await accountApi.getAccounts()
    if (res.code === 200 && res.data) {
      const accounts = res.data.map(account => {
        const updatedAccount = [...account]
        if (showPending) {
          updatedAccount[4] = -1 // -1 表示验证中的临时状态
        }
        return updatedAccount
      })
      accountStore.setAccounts(accounts)
    }
  } catch (error) {
    console.error('快速获取账号数据失败:', error)
  }
}

// 获取账号数据（带验证）
const fetchValidAccounts = async (accountStore, appStore) => {
  if (appStore.isAccountRefreshing) return
  appStore.setAccountRefreshing(true)

  try {
    const res = await accountApi.getValidAccounts()
    if (res.code === 200 && res.data) {
      accountStore.setAccounts(res.data)
      markCheckedToday()
      ElMessage.success('账号数据获取成功')
      if (appStore.isFirstTimeAccountManagement) {
        appStore.setAccountManagementVisited()
      }
    } else {
      ElMessage.error('获取账号数据失败')
    }
  } catch (error) {
    console.error('获取账号数据失败:', error)
    ElMessage.error('获取账号数据失败')
  } finally {
    appStore.setAccountRefreshing(false)
  }
}

// 后台验证所有账号（避免阻塞UI）
const validateAccountsInBackground = async (accountStore) => {
  try {
    const res = await accountApi.getValidAccounts()
    if (res.code === 200 && res.data) {
      accountStore.setAccounts(res.data)
      markCheckedToday()
    }
  } catch (error) {
    console.error('后台验证账号失败:', error)
  }
}

export function useAccountStatus() {
  const accountStore = useAccountStore()
  const appStore = useAppStore()
  const { nameOptions, fetchNameOptions } = createNameOptions()

  const fetchAccounts = () => fetchValidAccounts(accountStore, appStore)

  onMounted(() => {
    // 加载可选名称
    fetchNameOptions()

    // 每天只自动校验一次账号状态，其余时间直接展示上次的校验结果
    const autoCheckNeeded = shouldAutoCheckToday()
    fetchAccountsQuick(accountStore, autoCheckNeeded)

    if (autoCheckNeeded) {
      setTimeout(() => {
        validateAccountsInBackground(accountStore)
      }, 100)
    }
  })

  return { accountStore, appStore, nameOptions, fetchNameOptions, fetchAccounts }
}
