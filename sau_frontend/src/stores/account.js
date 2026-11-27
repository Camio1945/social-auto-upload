import { defineStore } from 'pinia'
import { ref } from 'vue'

// 平台类型映射（小红书已停用）
const PLATFORM_TYPES = {
  2: '视频号',
  3: '抖音',
  4: '快手'
}

// 转换后端返回的数组数据为前端使用的格式
const toAccountView = (item) => ({
  id: item[0],
  type: item[1],
  filePath: item[2],
  name: item[3],
  status: item[4] === -1 ? '验证中' : (item[4] === 1 ? '正常' : '异常'),
  lastCheckedAt: item[5] || '',
  platform: PLATFORM_TYPES[item[1]] || '未知'
})

export const useAccountStore = defineStore('account', () => {
  // 存储所有账号信息
  const accounts = ref([])

  // 设置账号列表
  const setAccounts = (accountsData) => {
    accounts.value = accountsData.map(toAccountView)
  }
  
  // 添加账号
  const addAccount = (account) => {
    accounts.value.push(account)
  }
  
  // 更新账号
  const updateAccount = (id, updatedAccount) => {
    const index = accounts.value.findIndex(acc => acc.id === id)
    if (index !== -1) {
      accounts.value[index] = { ...accounts.value[index], ...updatedAccount }
    }
  }
  
  // 删除账号
  const deleteAccount = (id) => {
    accounts.value = accounts.value.filter(acc => acc.id !== id)
  }
  
  // 根据平台获取账号
  const getAccountsByPlatform = (platform) => {
    return accounts.value.filter(acc => acc.platform === platform)
  }
  
  return {
    accounts,
    setAccounts,
    addAccount,
    updateAccount,
    deleteAccount,
    getAccountsByPlatform
  }
})