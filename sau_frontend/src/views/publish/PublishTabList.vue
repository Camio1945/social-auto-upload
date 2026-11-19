<template>
  <div class="tab-management">
    <div class="tab-header">
      <div class="tab-list">
        <div
          v-for="tab in publish.tabs"
          :key="tab.name"
          :class="['tab-item', { active: publish.activeTab === tab.name }]"
          @click="publish.activeTab = tab.name"
        >
          <span>{{ tab.label }}</span>
          <el-icon
            v-if="publish.tabs.length > 1"
            class="close-icon"
            @click.stop="publish.removeTab(tab.name)"
          >
            <Close />
          </el-icon>
        </div>
      </div>
      <div class="tab-actions">
        <el-button type="primary" size="small" @click="publish.addTab" class="add-tab-btn">
          <el-icon><Plus /></el-icon>
          添加Tab
        </el-button>
        <el-button
          type="success"
          size="small"
          @click="publish.batchPublish"
          :loading="publish.batchPublishing"
          class="batch-publish-btn"
        >
          批量发布
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Plus, Close } from '@element-plus/icons-vue'
import { usePublishContext } from '@/composables/publish/publishContext'

const publish = usePublishContext()
</script>
