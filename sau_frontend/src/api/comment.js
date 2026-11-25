import { http } from '@/utils/request'

// 评论管理相关API
export const commentApi = {
  // 启动同步任务（后台线程执行），type: 3 抖音 / 4 快手
  syncComments(type = 3) {
    return http.post('/syncComments', { type })
  },

  // 查询同步任务状态
  getSyncStatus() {
    return http.get('/getCommentSyncStatus')
  },

  // 获取评论列表与作品列表
  getComments(params) {
    return http.get('/getComments', params)
  },

  // 标记单条评论是否已处理
  markHandled(id, handled) {
    return http.post('/markCommentHandled', { id, handled })
  },

  // 回复一级评论（由用户确认后调用）
  replyComment(id, text) {
    return http.post('/replyComment', { id, text })
  },

  // 给评论点赞（已点赞的不允许再次点击）
  likeComment(id) {
    return http.post('/likeComment', { id })
  }
}
