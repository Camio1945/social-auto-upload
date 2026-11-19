<template>
  <el-dialog
    v-model="publish.materialLibraryVisible"
    title="选择素材"
    width="800px"
    class="material-library-dialog"
  >
    <div class="material-library-content">
      <el-checkbox-group v-model="publish.selectedMaterials">
        <div class="material-list">
          <div v-for="material in publish.materials" :key="material.id" class="material-item">
            <el-checkbox :label="material.id" class="material-checkbox">
              <div class="material-info">
                <div class="material-name">{{ material.filename }}</div>
                <div class="material-details">
                  <span class="file-size">{{ material.filesize }}MB</span>
                  <span class="upload-time">{{ material.upload_time }}</span>
                </div>
              </div>
            </el-checkbox>
          </div>
        </div>
      </el-checkbox-group>
    </div>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="publish.materialLibraryVisible = false">取消</el-button>
        <el-button type="primary" @click="publish.confirmMaterialSelection">确定</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { usePublishContext } from '@/composables/publish/publishContext'

const publish = usePublishContext()
</script>
