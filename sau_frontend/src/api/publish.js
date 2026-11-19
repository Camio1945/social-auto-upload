import { http } from '@/utils/request'

// 发布记录相关API
export const publishApi = {
  // 获取发布记录（按时间倒序）
  getPublishLogs(limit = 200) {
    return http.get('/getPublishLogs', { limit })
  }
}
