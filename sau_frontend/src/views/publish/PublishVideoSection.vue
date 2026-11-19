<template>
  <div class="upload-section">
    <h3>视频</h3>
    <div class="upload-options">
      <el-button type="primary" @click="publish.showUploadOptions(tab)" class="upload-btn">
        <el-icon><Upload /></el-icon>
        上传视频
      </el-button>
    </div>

    <!-- 已上传文件列表 -->
    <div v-if="tab.fileList.length > 0" class="uploaded-files">
      <h4>已上传文件：</h4>
      <div class="file-list">
        <div v-for="(file, index) in tab.fileList" :key="index" class="file-item">
          <el-link :href="file.url" target="_blank" type="primary">{{ file.name }}</el-link>
          <span class="file-size">{{ (file.size / 1024 / 1024).toFixed(2) }}MB</span>
          <el-button type="danger" size="small" @click="publish.removeFile(tab, index)">删除</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Upload } from '@element-plus/icons-vue'
import { usePublishContext } from '@/composables/publish/publishContext'

defineProps({
  tab: {
    type: Object,
    required: true
  }
})

const publish = usePublishContext()
</script>
