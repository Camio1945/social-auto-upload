import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { materialApi } from '@/api/material'

// API base URL
export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'

// 刷新tab的展示文件列表
const syncDisplayFileList = (tab) => {
  tab.displayFileList = tab.fileList.map(item => ({
    name: item.name,
    url: item.url
  }))
}

const createUploadState = (appStore) => {
  const uploadOptionsVisible = ref(false)
  const localUploadVisible = ref(false)
  const materialLibraryVisible = ref(false)
  const currentUploadTab = ref(null)
  const selectedMaterials = ref([])
  const materials = computed(() => appStore.materials)
  const authHeaders = computed(() => ({
    Authorization: `Bearer ${localStorage.getItem('token') || ''}`
  }))
  return {
    uploadOptionsVisible,
    localUploadVisible,
    materialLibraryVisible,
    currentUploadTab,
    selectedMaterials,
    materials,
    authHeaders
  }
}

const createFileActions = (state) => {
  // 显示上传选项
  const showUploadOptions = (tab) => {
    state.currentUploadTab.value = tab
    state.uploadOptionsVisible.value = true
  }

  // 选择本地上传
  const selectLocalUpload = () => {
    state.uploadOptionsVisible.value = false
    state.localUploadVisible.value = true
  }

  // 处理文件上传成功
  const handleUploadSuccess = (response, file, tab) => {
    if (response.code !== 200) {
      ElMessage.error(response.msg || '上传失败')
      return
    }
    const filePath = response.data.path || response.data
    tab.fileList.push({
      name: file.name,
      url: materialApi.getMaterialPreviewUrl(filePath.split('/').pop()),
      path: filePath,
      size: file.size,
      type: file.type
    })
    syncDisplayFileList(tab)
    ElMessage.success('文件上传成功')
  }

  // 处理文件上传失败
  const handleUploadError = () => {
    ElMessage.error('文件上传失败')
  }

  // 删除已上传文件
  const removeFile = (tab, index) => {
    tab.fileList.splice(index, 1)
    syncDisplayFileList(tab)
    ElMessage.success('文件删除成功')
  }

  return { showUploadOptions, selectLocalUpload, handleUploadSuccess, handleUploadError, removeFile }
}

// 将素材添加到tab的文件列表（去重）
const addMaterialToTab = (tab, material) => {
  const fileInfo = {
    name: material.filename,
    url: materialApi.getMaterialPreviewUrl(material.file_path.split('/').pop()),
    path: material.file_path,
    size: material.filesize * 1024 * 1024, // 转换为字节
    type: 'video/mp4'
  }
  const exists = tab.fileList.some(file => file.path === fileInfo.path)
  if (!exists) tab.fileList.push(fileInfo)
}

// 把选中的素材写入当前tab（自动去重）
const applyMaterialsToTab = (state) => {
  const tab = state.currentUploadTab.value
  if (!tab) return
  state.selectedMaterials.value.forEach(materialId => {
    const material = state.materials.value.find(m => m.id === materialId)
    if (material) addMaterialToTab(tab, material)
  })
  syncDisplayFileList(tab)
}

const createMaterialActions = (state, appStore) => {
  // 选择素材库
  const selectMaterialLibrary = async () => {
    state.uploadOptionsVisible.value = false
    if (state.materials.value.length === 0) {
      try {
        const response = await materialApi.getAllMaterials()
        if (response.code !== 200) {
          ElMessage.error('获取素材列表失败')
          return
        }
        appStore.setMaterials(response.data)
      } catch (error) {
        console.error('获取素材列表出错:', error)
        ElMessage.error('获取素材列表失败')
        return
      }
    }
    state.selectedMaterials.value = []
    state.materialLibraryVisible.value = true
  }

  // 确认素材选择
  const confirmMaterialSelection = () => {
    if (state.selectedMaterials.value.length === 0) {
      ElMessage.warning('请选择至少一个素材')
      return
    }
    applyMaterialsToTab(state)
    const addedCount = state.selectedMaterials.value.length
    state.materialLibraryVisible.value = false
    state.selectedMaterials.value = []
    state.currentUploadTab.value = null
    ElMessage.success(`已添加 ${addedCount} 个素材`)
  }

  return { selectMaterialLibrary, confirmMaterialSelection }
}

export function usePublishUpload() {
  const appStore = useAppStore()
  const state = createUploadState(appStore)
  return {
    apiBaseUrl,
    ...state,
    ...createFileActions(state),
    ...createMaterialActions(state, appStore)
  }
}
