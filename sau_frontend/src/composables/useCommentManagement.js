import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { commentApi } from '@/api/comment'

// 评论管理页的状态与操作，按职责拆成多个组合函数

function createCommentStats(posts, syncStatus) {
  const totalSaved = computed(() =>
    posts.value.reduce((sum, post) => sum + (post.savedCount || 0), 0)
  )
  const unhandledTotal = computed(() =>
    posts.value.reduce((sum, post) => sum + (post.unhandledCount || 0), 0)
  )
  const syncPercent = computed(() => {
    const { current, total } = syncStatus.value
    if (!total) return 0
    return Math.min(100, Math.round((current / total) * 100))
  })
  return { totalSaved, unhandledTotal, syncPercent }
}

function createCommentState() {
  const comments = ref([])
  const posts = ref([])
  const platformType = ref(3)
  const handledFilter = ref('')
  const postFilter = ref(null)
  const syncStatus = ref({
    running: false,
    type: null,
    phase: '',
    current: 0,
    total: 0,
    message: '',
    error: null,
    truncated: [],
    finishedAt: null
  })
  // 与后端 MAX_COMMENT_PAGES 保持一致，仅用于提示文案
  const maxCommentPages = 20
  const platformNames = { 2: '视频号', 3: '抖音', 4: '快手' }
  const platformName = computed(() => platformNames[platformType.value] || '未知平台')
  const stats = createCommentStats(posts, syncStatus)
  return {
    comments,
    posts,
    platformType,
    platformName,
    handledFilter,
    postFilter,
    syncStatus,
    maxCommentPages,
    ...stats
  }
}

function useCommentList(state) {
  const fetchComments = async () => {
    try {
      const res = await commentApi.getComments({
        type: state.platformType.value,
        handled: state.handledFilter.value,
        postId: state.postFilter.value || undefined
      })
      if (res.code === 200 && res.data) {
        state.comments.value = res.data.comments || []
        state.posts.value = res.data.posts || []
      }
    } catch (error) {
      console.error('获取评论失败:', error)
    }
  }
  return { fetchComments }
}

function useCommentHandled(fetchComments) {
  const handlingId = ref(null)
  const toggleHandled = async (row, value) => {
    handlingId.value = row.id
    try {
      await commentApi.markHandled(row.id, value)
      row.isHandled = value ? 1 : 0
      await fetchComments()
    } catch (error) {
      console.error('更新评论状态失败:', error)
    } finally {
      handlingId.value = null
    }
  }
  return { handlingId, toggleHandled }
}

function useCommentSync(state, fetchComments) {
  let pollTimer = null

  const stopPolling = () => {
    if (!pollTimer) return
    clearInterval(pollTimer)
    pollTimer = null
  }

  const applyStatus = async (data) => {
    state.syncStatus.value = data
    if (data.running) return
    const wasRunning = pollTimer !== null
    stopPolling()
    const samePlatform = !data.type || data.type === state.platformType.value
    if (wasRunning && samePlatform) await fetchComments()
  }

  const pollStatus = async () => {
    try {
      const res = await commentApi.getSyncStatus()
      if (res.code === 200 && res.data) await applyStatus(res.data)
    } catch (error) {
      console.error('获取同步状态失败:', error)
    }
  }

  const startTimer = () => {
    stopPolling()
    pollTimer = setInterval(pollStatus, 2000)
  }

  const startSync = async () => {
    if (state.syncStatus.value.running) return
    try {
      await commentApi.syncComments(state.platformType.value)
      ElMessage.success('同步任务已启动')
      await pollStatus()
      startTimer()
    } catch (error) {
      console.error('启动同步失败:', error)
    }
  }

  return { stopPolling, pollStatus, startTimer, startSync }
}

function useCommentLike(fetchComments) {
  const likingId = ref(null)
  const likeComment = async (row) => {
    likingId.value = row.id
    try {
      await commentApi.likeComment(row.id)
      ElMessage.success('点赞成功')
      await fetchComments()
    } catch (error) {
      console.error('点赞失败:', error)
    } finally {
      likingId.value = null
    }
  }
  return { likingId, likeComment }
}

function useCommentReply(fetchComments) {
  const replyVisible = ref(false)
  const replyTarget = ref({})
  const replyText = ref('')
  const replying = ref(false)

  const openReply = (row) => {
    replyTarget.value = row
    replyText.value = ''
    replyVisible.value = true
  }

  // 抖音回复为单行文本：输入和粘贴时直接拦掉换行与 @
  const normalizeReplyText = (value) => {
    replyText.value = (value || '').replace(/[\r\n@]/g, '')
  }

  const sendReply = async (text) => {
    replying.value = true
    try {
      await commentApi.replyComment(replyTarget.value.id, text)
      ElMessage.success('回复成功，已自动标记为已处理')
      replyVisible.value = false
      await fetchComments()
    } catch (error) {
      console.error('回复评论失败:', error)
    } finally {
      replying.value = false
    }
  }

  const confirmReply = async () => {
    const text = replyText.value.trim()
    if (!text) {
      ElMessage.warning('请输入回复内容')
      return
    }
    await sendReply(text)
  }

  return {
    replyVisible, replyTarget, replyText, replying,
    openReply, normalizeReplyText, confirmReply
  }
}

// 评论管理页入口：组合列表、已处理、同步、点赞与回复
export function useCommentManagement() {
  const state = createCommentState()
  const { fetchComments } = useCommentList(state)
  const handled = useCommentHandled(fetchComments)
  const sync = useCommentSync(state, fetchComments)
  const like = useCommentLike(fetchComments)
  const reply = useCommentReply(fetchComments)

  const changePlatform = () => {
    state.postFilter.value = null
    return fetchComments()
  }

  onMounted(async () => {
    await fetchComments()
    await sync.pollStatus()
    if (state.syncStatus.value.running) sync.startTimer()
  })
  onUnmounted(sync.stopPolling)

  return { ...state, ...handled, ...sync, ...like, ...reply, fetchComments, changePlatform }
}
