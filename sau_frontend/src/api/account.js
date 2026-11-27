import { http } from '@/utils/request'

// 账号管理相关API
export const accountApi = {
  // 获取有效账号列表（带验证）
  getValidAccounts() {
    return http.get('/getValidAccounts')
  },

  // 获取账号列表（不带验证，快速加载）
  getAccounts() {
    return http.get('/getAccounts')
  },

  // 添加账号
  addAccount(data) {
    return http.post('/account', data)
  },

  // 更新账号
  updateAccount(data) {
    return http.post('/updateUserinfo', data)
  },

  // 使用已保存的 Cookie 打开平台发布页
  openAccount(id) {
    return http.post('/openAccount', { id })
  },

  // 删除账号
  deleteAccount(id) {
    return http.get(`/deleteAccount?id=${id}`)
  },

  // 视频号登录态保活配置
  getKeepaliveConfig() {
    return http.get('/keepalive/config')
  },

  // 更新保活开关与间隔
  updateKeepaliveConfig(data) {
    return http.post('/keepalive/config', data)
  },

  // 立即执行一次保活
  runKeepalive() {
    return http.post('/keepalive/run')
  }
}