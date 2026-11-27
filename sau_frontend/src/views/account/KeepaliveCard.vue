<template>
  <div class="keepalive-card">
    <div class="keepalive-head">
      <div class="keepalive-text">
        <span class="keepalive-title">视频号登录态保活</span>
        <span class="keepalive-desc">
          按设定间隔用无窗口浏览器访问一次视频号页面并刷新 Cookie，降低长时间不活跃导致的失效。
        </span>
      </div>
      <el-switch v-model="enabled" :loading="saving" @change="handleToggle" />
    </div>

    <div class="keepalive-body">
      <div class="keepalive-row">
        <span class="label">保活间隔</span>
        <el-input-number
          v-model="intervalMinutes"
          :min="10"
          :max="1440"
          :step="10"
          :disabled="saving"
          size="small"
          @change="handleIntervalChange"
        />
        <span class="unit">分钟</span>
        <el-button size="small" :loading="running" :disabled="!enabled" @click="handleRunNow">
          立即保活
        </el-button>
      </div>

      <div class="keepalive-row keepalive-status">
        <span class="label">上次执行</span>
        <span class="value">{{ lastRunText }}</span>
      </div>
      <div class="keepalive-row keepalive-status">
        <span class="label">下次执行</span>
        <span class="value">{{ nextRunText }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { accountApi } from '@/api/account'

const RESULT_TEXT = {
  ok: '成功',
  invalid: '登录态失效',
  busy: '正在执行',
  skipped: '已跳过',
  error: '出错'
}

const emit = defineEmits(['done'])

const enabled = ref(false)
const intervalMinutes = ref(60)
const saving = ref(false)
const running = ref(false)
const lastRunAt = ref('')
const lastResult = ref('')
const lastMessage = ref('')
const nextRunAt = ref('')

const applyConfig = (config) => {
  if (!config) return
  enabled.value = Boolean(config.enabled)
  intervalMinutes.value = config.intervalMinutes || 60
  lastRunAt.value = config.lastRunAt || ''
  lastResult.value = config.lastResult || ''
  lastMessage.value = config.lastMessage || ''
  nextRunAt.value = config.nextRunAt || ''
}

const lastRunText = computed(() => {
  if (!lastRunAt.value) return '尚未执行'
  const result = RESULT_TEXT[lastResult.value] || lastResult.value
  const detail = lastMessage.value ? `（${lastMessage.value}）` : ''
  return `${lastRunAt.value}　${result}${detail}`
})

const nextRunText = computed(() => {
  if (!enabled.value) return '保活已关闭'
  return nextRunAt.value || '调度中'
})

const loadConfig = async () => {
  try {
    const res = await accountApi.getKeepaliveConfig()
    applyConfig(res.data)
  } catch (error) {
    console.error('获取保活配置失败:', error)
  }
}

const saveConfig = async (payload) => {
  saving.value = true
  try {
    const res = await accountApi.updateKeepaliveConfig(payload)
    applyConfig(res.data)
    ElMessage.success('保活配置已更新')
  } catch (error) {
    console.error('更新保活配置失败:', error)
    await loadConfig()
  } finally {
    saving.value = false
  }
}

const handleToggle = (value) => saveConfig({ enabled: value })

const handleIntervalChange = (value) => {
  if (!value) return
  saveConfig({ intervalMinutes: value })
}

const handleRunNow = async () => {
  running.value = true
  try {
    const res = await accountApi.runKeepalive()
    const outcome = res.data || {}
    if (outcome.result === 'ok') {
      ElMessage.success(outcome.message || '保活成功')
    } else if (outcome.result === 'busy') {
      ElMessage.warning(outcome.message || '上一次保活仍在执行')
    } else {
      ElMessage.error(outcome.message || '保活失败')
    }
    await loadConfig()
    emit('done')
  } catch (error) {
    console.error('执行保活失败:', error)
  } finally {
    running.value = false
  }
}

onMounted(loadConfig)
</script>

<style lang="scss" scoped>
.keepalive-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 4px;
  padding: 12px 16px;
  margin-bottom: 12px;
  background-color: var(--el-fill-color-blank);

  .keepalive-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
  }

  .keepalive-text {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .keepalive-title {
    font-weight: 600;
  }

  .keepalive-desc {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .keepalive-body {
    margin-top: 10px;
  }

  .keepalive-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;

    & + .keepalive-row {
      margin-top: 8px;
    }
  }

  .label {
    width: 64px;
    color: var(--el-text-color-secondary);
  }

  .unit {
    color: var(--el-text-color-secondary);
  }

  .keepalive-status .value {
    color: var(--el-text-color-regular);
  }
}
</style>
