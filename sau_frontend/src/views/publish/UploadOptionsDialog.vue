<template>
  <el-dialog
    v-model="publish.uploadOptionsVisible"
    title="选择上传方式"
    width="400px"
    class="upload-options-dialog"
  >
    <div class="upload-options-content">
      <el-button type="primary" @click="publish.selectLocalUpload" class="option-btn">
        <el-icon><Upload /></el-icon>
        本地上传
      </el-button>
      <el-button type="success" @click="publish.selectMaterialLibrary" class="option-btn">
        <el-icon><Folder /></el-icon>
        素材库
      </el-button>
    </div>
  </el-dialog>
</template>

<script setup>
import { Upload, Folder } from '@element-plus/icons-vue'
import { usePublishContext } from '@/composables/publish/publishContext'

const publish = usePublishContext()
</script>
