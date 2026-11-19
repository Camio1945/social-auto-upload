<template>
  <el-dialog
    v-model="publish.localUploadVisible"
    title="本地上传"
    width="600px"
    class="local-upload-dialog"
  >
    <el-upload
      class="video-upload"
      drag
      :auto-upload="true"
      :action="`${publish.apiBaseUrl}/upload`"
      :on-success="handleUploadSuccess"
      :on-error="publish.handleUploadError"
      multiple
      accept="video/*"
      :headers="publish.authHeaders"
    >
      <el-icon class="el-icon--upload"><Upload /></el-icon>
      <div class="el-upload__text">
        将视频文件拖到此处，或<em>点击上传</em>
      </div>
      <template #tip>
        <div class="el-upload__tip">支持MP4、AVI等视频格式，可上传多个文件</div>
      </template>
    </el-upload>
  </el-dialog>
</template>

<script setup>
import { Upload } from '@element-plus/icons-vue'
import { usePublishContext } from '@/composables/publish/publishContext'

const publish = usePublishContext()

const handleUploadSuccess = (response, file) => {
  publish.handleUploadSuccess(response, file, publish.currentUploadTab)
}
</script>
