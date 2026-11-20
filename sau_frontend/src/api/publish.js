import { http } from '@/utils/request'

// 发布记录相关API
export const publishApi = {
  // 获取发布记录（按时间倒序）
  getPublishLogs(limit = 200) {
    return http.get('/getPublishLogs', { limit })
  },

  // 重新发布一条失败的记录（复用发布接口）
  retryPublish(payload) {
    return http.post('/postVideo', payload)
  }
}
