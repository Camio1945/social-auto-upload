<template>
  <el-table :data="accounts" style="width: 100%">
    <el-table-column label="头像" width="80">
      <template #default="scope">
        <el-avatar :src="getDefaultAvatar(scope.row.name)" :size="40" />
      </template>
    </el-table-column>
    <el-table-column prop="name" label="名称" width="180" />
    <el-table-column prop="platform" label="平台">
      <template #default="scope">
        <el-tag :type="getPlatformTagType(scope.row.platform)" effect="plain">
          {{ scope.row.platform }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="status" label="状态">
      <template #default="scope">
        <el-tag
          :type="getStatusTagType(scope.row.status)"
          effect="plain"
          :class="{ 'clickable-status': isStatusClickable(scope.row.status) }"
          @click="emit('status-click', scope.row)"
        >
          <el-icon v-if="scope.row.status === '验证中'" class="is-loading">
            <Loading />
          </el-icon>
          {{ scope.row.status }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="420">
      <template #default="scope">
        <el-button size="small" @click="emit('edit', scope.row)">编辑</el-button>
        <el-button size="small" type="primary" :icon="Download" @click="emit('download', scope.row)">
          下载Cookie
        </el-button>
        <el-button size="small" type="info" :icon="Upload" @click="emit('upload', scope.row)">
          上传Cookie
        </el-button>
        <el-button size="small" type="danger" @click="emit('delete', scope.row)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup>
import { Download, Upload, Loading } from '@element-plus/icons-vue'

defineProps({
  accounts: {
    type: Array,
    required: true
  }
})

const emit = defineEmits(['edit', 'download', 'upload', 'delete', 'status-click'])

// 获取默认头像
const getDefaultAvatar = (name) => {
  return `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&background=random`
}

// 获取平台标签类型
const getPlatformTagType = (platform) => {
  const typeMap = {
    '快手': 'success',
    '抖音': 'danger',
    '视频号': 'warning',
    '小红书': 'info'
  }
  return typeMap[platform] || 'info'
}

// 判断状态是否可点击（仅异常状态可点击以重新登录）
const isStatusClickable = (status) => {
  return status === '异常'
}

// 获取状态标签类型
const getStatusTagType = (status) => {
  if (status === '验证中') {
    return 'info'
  } else if (status === '正常') {
    return 'success'
  }
  return 'danger'
}
</script>

<style lang="scss" scoped>
.clickable-status {
  cursor: pointer;
  transition: all 0.3s;

  &:hover {
    transform: scale(1.05);
    box-shadow: 0 0 8px rgba(0, 0, 0, 0.15);
  }
}
</style>
