<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="500px"
    :close-on-click-modal="false"
    :close-on-press-escape="!sseConnecting"
    :show-close="!sseConnecting"
  >
    <el-form :model="form" label-width="80px" :rules="rules" ref="accountFormRef">
      <el-form-item label="平台" prop="platform">
        <el-radio-group v-model="form.platform" :disabled="type !== 'add' || sseConnecting">
          <el-radio-button value="抖音">抖音</el-radio-button>
          <el-radio-button value="快手">快手</el-radio-button>
          <el-radio-button value="视频号">视频号</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="名称" prop="name">
        <el-radio-group
          v-model="form.name"
          :disabled="sseConnecting || type !== 'add'"
          class="name-radio-group"
        >
          <el-radio
            v-for="item in nameOptions"
            :key="item.id"
            :value="item.userName"
          >
            {{ item.userName }}
          </el-radio>
        </el-radio-group>
        <div v-if="nameHint" class="name-empty-tip">
          {{ nameHint }}
        </div>
      </el-form-item>

      <!-- 二维码显示区域 -->
      <div v-if="sseConnecting" class="qrcode-container">
        <div v-if="qrCodeData && !loginStatus" class="qrcode-wrapper">
          <p class="qrcode-tip">请使用对应平台APP扫描二维码登录</p>
          <img :src="qrCodeData" alt="登录二维码" class="qrcode-image" />
        </div>
        <div v-else-if="!qrCodeData && !loginStatus" class="loading-wrapper">
          <el-icon class="is-loading"><Refresh /></el-icon>
          <span>请求中...</span>
        </div>
        <div v-else-if="loginStatus === '200'" class="success-wrapper">
          <el-icon><CircleCheckFilled /></el-icon>
          <span>{{ isAdd ? '添加成功' : '重新登录成功' }}</span>
        </div>
        <div v-else-if="loginStatus === '500'" class="error-wrapper">
          <el-icon><CircleCloseFilled /></el-icon>
          <span>{{ isAdd ? '添加失败' : '重新登录失败' }}，请稍后再试</span>
        </div>
      </div>
    </el-form>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="visible = false">{{ isAdd ? '取消' : '关闭' }}</el-button>
        <el-button
          v-if="!isRelogin"
          type="primary"
          @click="confirm"
          :loading="sseConnecting"
          :disabled="sseConnecting || nameOptions.length === 0"
        >
          {{ sseConnecting ? '请求中' : '确认' }}
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Refresh, CircleCheckFilled, CircleCloseFilled } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  type: { type: String, required: true },
  form: { type: Object, required: true },
  rules: { type: Object, required: true },
  nameOptions: { type: Array, required: true },
  nameHint: { type: String, default: '' },
  sseConnecting: { type: Boolean, default: false },
  qrCodeData: { type: String, default: '' },
  loginStatus: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue', 'submit'])

const accountFormRef = ref(null)

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const isAdd = computed(() => props.type === 'add')
const isRelogin = computed(() => props.type === 'relogin')

// 弹窗标题按当前模式显示
const dialogTitle = computed(() => {
  if (isAdd.value) return '添加账号'
  return isRelogin.value ? '重新登录' : '编辑账号'
})

// 校验通过后交给父组件执行添加或保存
const confirm = () => {
  accountFormRef.value.validate((valid) => {
    if (valid) emit('submit')
  })
}
</script>

<style lang="scss" scoped>
@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.name-radio-group {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;

  :deep(.el-radio) {
    margin-right: 0;
  }
}

.name-empty-tip {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.4;
  color: var(--el-text-color-secondary);
}

.qrcode-container {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 250px;

  .qrcode-wrapper {
    text-align: center;

    .qrcode-tip {
      margin-bottom: 15px;
      color: #606266;
    }

    .qrcode-image {
      max-width: 200px;
      max-height: 200px;
      border: 1px solid #ebeef5;
      background-color: black;
    }
  }

  .loading-wrapper,
  .success-wrapper,
  .error-wrapper {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;

    .el-icon {
      font-size: 48px;

      &.is-loading {
        animation: rotate 1s linear infinite;
      }
    }

    span {
      font-size: 16px;
    }
  }

  .success-wrapper .el-icon {
    color: #67c23a;
  }

  .error-wrapper .el-icon {
    color: #f56c6c;
  }
}
</style>
