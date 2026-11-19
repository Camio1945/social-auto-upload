import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { materialApi } from '@/api/material'

// API base URL
export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'

// 刷新展示用文件列表
const syncDisplayFileList = (form) => {
  form.displayFileList = form.fileList.map(item => ({
    name: item.name,
    url: item.url
  }))
}

// 文件名格式：<序号>.<名称>.<扩展名>，例如 0002.AI退潮的账别算在黄仁勋头上.mp4
const FILE_NAME_PATTERN = /^\d+\.(.+)\.[^.]+$/

// 若文件名符合格式，则自动把中间的名称填入标题
const applyTitleFromFileName = (form, fileName) => {
  const match = FILE_NAME_PATTERN.exec(fileName || '')
  if (match) form.title = match[1]
}

// 将素材添加到文件列表（去重），返回是否添加成功
const addMaterialToForm = (form, material) => {
  const fileInfo = {
    name: material.filename,
    url: materialApi.getMaterialPreviewUrl(material.file_path.split('/').pop()),
    path: material.file_path,
    size: material.filesize * 1024 * 1024, // 转换为字节
    type: 'video/mp4'
  }
  const exists = form.fileList.some(file => file.path === fileInfo.path)
  if (exists) return false
  form.fileList.push(fileInfo)
  return true
}

// 把选中的素材写入文件列表，并用第一个符合命名格式的素材名填写标题
const applySelectedMaterials = (form, selectedMaterialIds, materials) => {
  const addedMaterials = []
  selectedMaterialIds.forEach(materialId => {
    const material = materials.find(m => m.id === materialId)
    if (material && addMaterialToForm(form, material)) {
      addedMaterials.push(material)
    }
  })
  syncDisplayFileList(form)
  const matched = addedMaterials.find(item => FILE_NAME_PATTERN.test(item.filename))
  if (matched) applyTitleFromFileName(form, matched.filename)
}

// 上传弹窗与文件操作
const createFileActions = (form, state) => {
  const showUploadOptions = () => {
    state.uploadOptionsVisible.value = true
  }

  const selectLocalUpload = () => {
    state.uploadOptionsVisible.value = false
    state.localUploadVisible.value = true
  }

  const handleUploadSuccess = (response, file) => {
    if (response.code !== 200) {
      ElMessage.error(response.msg || '上传失败')
      return
    }
    const filePath = response.data.path || response.data
    form.fileList.push({
      name: file.name,
      url: materialApi.getMaterialPreviewUrl(filePath.split('/').pop()),
      path: filePath,
      size: file.size,
      type: file.type
    })
    syncDisplayFileList(form)
    // 文件名符合 <序号>.<名称>.<扩展名> 时自动填写标题
    applyTitleFromFileName(form, file.name)
    ElMessage.success('文件上传成功')
  }

  const handleUploadError = () => {
    ElMessage.error('文件上传失败')
  }

  const removeFile = (index) => {
    form.fileList.splice(index, 1)
    syncDisplayFileList(form)
    ElMessage.success('文件删除成功')
  }

  return { showUploadOptions, selectLocalUpload, handleUploadSuccess, handleUploadError, removeFile }
}

// 素材库相关操作
const createMaterialActions = (form, state, appStore) => {
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

  const confirmMaterialSelection = () => {
    if (state.selectedMaterials.value.length === 0) {
      ElMessage.warning('请选择至少一个素材')
      return
    }
    applySelectedMaterials(form, state.selectedMaterials.value, state.materials.value)
    ElMessage.success(`已添加 ${state.selectedMaterials.value.length} 个素材`)
    state.materialLibraryVisible.value = false
    state.selectedMaterials.value = []
  }

  return { selectMaterialLibrary, confirmMaterialSelection }
}

// 创建上传相关的响应式状态
const createUploadState = () => {
  const appStore = useAppStore()
  const state = {
    uploadOptionsVisible: ref(false),
    localUploadVisible: ref(false),
    materialLibraryVisible: ref(false),
    selectedMaterials: ref([]),
    materials: computed(() => appStore.materials),
    authHeaders: computed(() => ({
      Authorization: `Bearer ${localStorage.getItem('token') || ''}`
    }))
  }
  return { appStore, state }
}

export function usePublishUpload(form) {
  const { appStore, state } = createUploadState()
  return {
    apiBaseUrl,
    ...state,
    ...createFileActions(form, state),
    ...createMaterialActions(form, state, appStore)
  }
}
