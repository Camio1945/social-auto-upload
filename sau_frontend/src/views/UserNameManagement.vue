<template>
  <div class="user-name-management">
    <div class="user-name-list-container">
      <div class="toolbar">
        <el-input
          v-model="searchKeyword"
          placeholder="输入名称搜索"
          prefix-icon="Search"
          clearable
        />
        <div class="action-buttons">
          <el-button type="primary" @click="handleAdd">添加名称</el-button>
          <el-button type="info" @click="fetchNames" :loading="loading">
            <el-icon :class="{ 'is-loading': loading }"><Refresh /></el-icon>
          </el-button>
        </div>
      </div>

      <el-table v-if="filteredNames.length > 0" :data="filteredNames" style="width: 100%">
        <el-table-column prop="id" label="ID" width="100" />
        <el-table-column prop="userName" label="名称" />
        <el-table-column label="操作" width="200">
          <template #default="scope">
            <el-button size="small" @click="handleEdit(scope.row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-else class="empty-data">
        <el-empty description="暂无名称数据" />
      </div>
    </div>

    <!-- 添加/编辑名称对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogType === 'add' ? '添加名称' : '编辑名称'"
      width="460px"
      :close-on-click-modal="false"
    >
      <el-form :model="nameForm" label-width="80px" :rules="rules" ref="nameFormRef">
        <el-form-item label="名称" prop="userName">
          <el-input
            v-model="nameForm.userName"
            placeholder="请输入名称"
            maxlength="50"
            @keyup.enter="submitForm"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="submitForm">
            {{ submitting ? '提交中' : '确认' }}
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { userNameApi } from '@/api/userName'

// 名称列表
const names = ref([])
const loading = ref(false)
const searchKeyword = ref('')

// 对话框相关
const dialogVisible = ref(false)
const dialogType = ref('add') // 'add' 或 'edit'
const submitting = ref(false)
const nameFormRef = ref(null)
const nameForm = reactive({
  id: null,
  userName: ''
})

// 表单验证规则
const rules = {
  userName: [{ required: true, message: '请输入名称', trigger: 'blur' }]
}

// 过滤后的名称列表
const filteredNames = computed(() => {
  if (!searchKeyword.value) return names.value
  return names.value.filter(item => item.userName.includes(searchKeyword.value))
})

// 获取名称列表
const fetchNames = async () => {
  if (loading.value) return
  loading.value = true
  try {
    const res = await userNameApi.getUserNames()
    if (res.code === 200 && res.data) {
      names.value = res.data
    }
  } catch (error) {
    console.error('获取名称列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 打开添加对话框
const handleAdd = () => {
  dialogType.value = 'add'
  Object.assign(nameForm, { id: null, userName: '' })
  dialogVisible.value = true
}

// 打开编辑对话框
const handleEdit = (row) => {
  dialogType.value = 'edit'
  Object.assign(nameForm, { id: row.id, userName: row.userName })
  dialogVisible.value = true
}

// 删除名称
const handleDelete = (row) => {
  ElMessageBox.confirm(
    `确定要删除名称 ${row.userName} 吗？`,
    '警告',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  )
    .then(async () => {
      const res = await userNameApi.deleteUserName(row.id)
      if (res.code === 200) {
        ElMessage.success('删除成功')
        fetchNames()
      }
    })
    .catch(() => {})
}

// 提交表单
const submitForm = () => {
  nameFormRef.value.validate(async (valid) => {
    if (!valid || submitting.value) return

    submitting.value = true
    try {
      const userName = nameForm.userName.trim()
      const res = dialogType.value === 'add'
        ? await userNameApi.addUserName({ userName })
        : await userNameApi.updateUserName({ id: nameForm.id, userName })

      if (res.code === 200) {
        ElMessage.success(dialogType.value === 'add' ? '添加成功' : '更新成功')
        dialogVisible.value = false
        fetchNames()
      }
    } catch (error) {
      // 错误信息已由请求拦截器提示
    } finally {
      submitting.value = false
    }
  })
}

onMounted(() => {
  fetchNames()
})
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.user-name-management {
  .user-name-list-container {
    background-color: var(--el-bg-color);
    border-radius: 4px;
    box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
    padding: 20px;

    .toolbar {
      display: flex;
      justify-content: space-between;
      margin-bottom: 20px;

      .el-input {
        width: 300px;
      }

      .action-buttons {
        display: flex;
        gap: 10px;

        .el-icon.is-loading {
          animation: rotate 1s linear infinite;
        }
      }
    }

    .empty-data {
      padding: 40px 0;
    }
  }
}
</style>
