import { http } from '@/utils/request'

// 名称管理相关API（user_name 表）
export const userNameApi = {
  // 获取全部名称
  getUserNames() {
    return http.get('/getUserNames')
  },

  // 新增名称
  addUserName(data) {
    return http.post('/addUserName', data)
  },

  // 修改名称（会同步更新引用该名称的账号）
  updateUserName(data) {
    return http.post('/updateUserName', data)
  },

  // 删除名称（仍被账号使用时后端会拒绝）
  deleteUserName(id) {
    return http.get('/deleteUserName', { id })
  }
}
