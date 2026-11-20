import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { accountApi } from '@/api/account'
import { http } from '@/utils/request'
import { useAccountStore } from '@/stores/account'

// 平台名称与后端 type 的对应关系
const platformTypeMap = { '小红书': 1, '视频号': 2, '抖音': 3, '快手': 4 }
const LOGIN_SUCCESS_DELAY = 1000
const LOGIN_FAIL_RESET_DELAY = 2000

const getApiBaseUrl = () => import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'

// 对话框的基础状态
const createDialogState = () => {
  const dialogVisible = ref(false)
  const dialogType = ref('add') // 'add' 或 'edit'
  const accountForm = reactive({ id: null, name: '', platform: '', status: '正常' })
  const sseConnecting = ref(false)
  const qrCodeData = ref('')
  const loginStatus = ref('')
  const eventSource = ref(null)
  const rules = {
    platform: [{ required: true, message: '请选择平台', trigger: 'change' }],
    name: [{ required: true, message: '请选择账号名称', trigger: 'change' }]
  }
  return { dialogVisible, dialogType, accountForm, sseConnecting, qrCodeData, loginStatus, eventSource, rules }
}

// 按平台过滤可选名称：同一名称在同一平台只能有一个账号
const createNameAvailability = (state, accountStore, nameOptions) => {
  const usedNamesForPlatform = computed(() => new Set(
    accountStore.accounts
      .filter(acc => acc.platform === state.accountForm.platform && acc.id !== state.accountForm.id)
      .map(acc => acc.name)
  ))

  const availableNameOptions = computed(() => {
    return nameOptions.value.filter(item => !usedNamesForPlatform.value.has(item.userName))
  })

  const nameHint = computed(() => {
    if (nameOptions.value.length === 0) return '暂无可选名称，请先在「名称管理」中添加'
    if (availableNameOptions.value.length === 0) return '该平台下所有名称均已有账号'
    return ''
  })

  watch(() => state.accountForm.platform, () => {
    if (!state.accountForm.name) return
    const stillAvailable = availableNameOptions.value
      .some(item => item.userName === state.accountForm.name)
    if (!stillAvailable) {
      state.accountForm.name = ''
    }
  })

  return { availableNameOptions, nameHint }
}

const closeSSE = (state) => {
  if (state.eventSource.value) {
    state.eventSource.value.close()
    state.eventSource.value = null
  }
}

const finishLogin = (state, ctx) => {
  setTimeout(() => {
    closeSSE(state)
    setTimeout(() => {
      state.dialogVisible.value = false
      state.sseConnecting.value = false
      ElMessage.success(state.dialogType.value === 'add' ? '账号添加成功' : '重新登录成功')
      ElMessage({ type: 'info', message: '正在同步账号信息...', duration: 0 })
      ctx.fetchAccounts().then(() => {
        ElMessage.closeAll()
        ElMessage.success('账号信息已更新')
      })
    }, LOGIN_SUCCESS_DELAY)
  }, LOGIN_SUCCESS_DELAY)
}

const handleSSEStatus = (state, ctx, data) => {
  state.loginStatus.value = data
  if (data === '200') {
    finishLogin(state, ctx)
    return
  }
  closeSSE(state)
  setTimeout(() => {
    state.sseConnecting.value = false
    state.qrCodeData.value = ''
    state.loginStatus.value = ''
  }, LOGIN_FAIL_RESET_DELAY)
}

const handleSSEMessage = (state, ctx, event) => {
  const data = event.data
  // 二维码数据是较长的 base64 字符串
  if (!state.qrCodeData.value && data.length > 100) {
    state.qrCodeData.value = data.startsWith('data:image') ? data : `data:image/png;base64,${data}`
    return
  }
  if (data === '200' || data === '500') {
    handleSSEStatus(state, ctx, data)
  }
}

const connectSSE = (state, ctx, platform, name, accountId) => {
  closeSSE(state)
  state.sseConnecting.value = true
  state.qrCodeData.value = ''
  state.loginStatus.value = ''

  const type = platformTypeMap[platform] || 1
  const accountParam = accountId ? `&accountId=${encodeURIComponent(accountId)}` : ''
  const url = `${getApiBaseUrl()}/login?type=${type}&id=${encodeURIComponent(name)}${accountParam}`
  const source = new EventSource(url)
  state.eventSource.value = source

  source.onmessage = (event) => handleSSEMessage(state, ctx, event)
  source.onerror = () => {
    console.error('SSE连接错误:', source)
    ElMessage.error('连接服务器失败，请稍后再试')
    closeSSE(state)
    state.sseConnecting.value = false
  }
}

const handleAddAccount = (state, ctx) => {
  // 每次打开时刷新名称下拉，确保能选到「名称管理」中新建的名称
  ctx.fetchNameOptions()
  state.dialogType.value = 'add'
  Object.assign(state.accountForm, {
    id: null,
    name: '',
    platform: ctx.getDefaultPlatform(),
    status: '正常'
  })
  state.sseConnecting.value = false
  state.qrCodeData.value = ''
  state.loginStatus.value = ''
  state.dialogVisible.value = true
}

const handleEdit = (state, ctx, row) => {
  ctx.fetchNameOptions()
  state.dialogType.value = 'edit'
  Object.assign(state.accountForm, {
    id: row.id,
    name: row.name,
    platform: row.platform,
    status: row.status
  })
  state.dialogVisible.value = true
}

const handleReLogin = (state, ctx, row) => {
  state.dialogType.value = 'relogin'
  Object.assign(state.accountForm, {
    id: row.id,
    name: row.name,
    platform: row.platform,
    status: row.status
  })
  state.sseConnecting.value = false
  state.qrCodeData.value = ''
  state.loginStatus.value = ''
  state.dialogVisible.value = true
  setTimeout(() => connectSSE(state, ctx, row.platform, row.name, row.id), 300)
}

const handleStatusClick = (state, ctx, row) => {
  if (row.status !== '异常') return
  handleReLogin(state, ctx, row)
}

const handleDelete = (ctx, row) => {
  ElMessageBox.confirm(
    `确定要删除账号 ${row.name} 吗？`,
    '警告',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  )
    .then(async () => {
      try {
        const response = await accountApi.deleteAccount(row.id)
        if (response.code === 200) {
          ctx.accountStore.deleteAccount(row.id)
          ElMessage({ type: 'success', message: '删除成功' })
        } else {
          ElMessage.error(response.msg || '删除失败')
        }
      } catch (error) {
        console.error('删除账号失败:', error)
        ElMessage.error('删除账号失败')
      }
    })
    .catch(() => {})
}

const handleDownloadCookie = (row) => {
  const downloadUrl = `${getApiBaseUrl()}/downloadCookie?filePath=${encodeURIComponent(row.filePath)}`
  const link = document.createElement('a')
  link.href = downloadUrl
  link.download = `${row.name}_cookie.json`
  link.target = '_blank'
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

const uploadCookieFile = async (ctx, file, row) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('id', row.id)
  formData.append('platform', row.platform)
  try {
    await http.upload('/uploadCookie', formData)
    ElMessage.success('Cookie文件上传成功')
    ctx.fetchAccounts()
  } catch (error) {
    ElMessage.error('Cookie文件上传失败')
  }
}

const handleUploadCookie = (ctx, row) => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.style.display = 'none'
  document.body.appendChild(input)

  input.onchange = (event) => {
    const file = event.target.files[0]
    if (!file) {
      document.body.removeChild(input)
      return
    }
    if (!file.name.endsWith('.json')) {
      ElMessage.error('请选择JSON格式的Cookie文件')
      document.body.removeChild(input)
      return
    }
    uploadCookieFile(ctx, file, row).finally(() => document.body.removeChild(input))
  }

  input.click()
}

const saveAccountEdit = async (state, ctx) => {
  const type = platformTypeMap[state.accountForm.platform] || 1
  const res = await accountApi.updateAccount({
    id: state.accountForm.id,
    type,
    userName: state.accountForm.name
  })
  if (res.code !== 200) {
    ElMessage.error(res.msg || '更新账号失败')
    return
  }
  ctx.accountStore.updateAccount(state.accountForm.id, {
    id: state.accountForm.id,
    name: state.accountForm.name,
    platform: state.accountForm.platform,
    status: state.accountForm.status
  })
  ElMessage.success('更新成功')
  state.dialogVisible.value = false
  ctx.fetchAccounts()
}

const handleDialogSubmit = (state, ctx) => {
  if (state.dialogType.value === 'add') {
    connectSSE(state, ctx, state.accountForm.platform, state.accountForm.name)
    return
  }
  if (state.dialogType.value === 'relogin') return
  saveAccountEdit(state, ctx).catch((error) => {
    console.error('更新账号失败:', error)
    ElMessage.error('更新账号失败')
  })
}

export function useAccountDialog({ nameOptions, fetchNameOptions, fetchAccounts, getDefaultPlatform }) {
  const accountStore = useAccountStore()
  const state = createDialogState()
  const ctx = { accountStore, fetchNameOptions, fetchAccounts, getDefaultPlatform }
  const { availableNameOptions, nameHint } = createNameAvailability(state, accountStore, nameOptions)

  onBeforeUnmount(() => closeSSE(state))

  // 关闭弹窗时结束登录连接并重置状态
  watch(() => state.dialogVisible.value, (visible) => {
    if (visible) return
    closeSSE(state)
    state.sseConnecting.value = false
    state.qrCodeData.value = ''
    state.loginStatus.value = ''
  })

  return {
    ...state,
    availableNameOptions,
    nameHint,
    handleAddAccount: () => handleAddAccount(state, ctx),
    handleEdit: (row) => handleEdit(state, ctx, row),
    handleReLogin: (row) => handleReLogin(state, ctx, row),
    handleStatusClick: (row) => handleStatusClick(state, ctx, row),
    handleDelete: (row) => handleDelete(ctx, row),
    handleDownloadCookie: (row) => handleDownloadCookie(row),
    handleUploadCookie: (row) => handleUploadCookie(ctx, row),
    handleDialogSubmit: () => handleDialogSubmit(state, ctx)
  }
}
