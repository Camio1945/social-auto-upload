<template>
  <div class="platform-section">
    <h3>平台</h3>
    <div class="platform-summary">
      <template v-if="selectedPlatformList.length > 0">
        <el-tag
          v-for="item in selectedPlatformList"
          :key="item.key"
          effect="plain"
          class="platform-tag"
        >
          {{ item.name }}
        </el-tag>
      </template>
      <span v-else class="platform-hint">选择账号后自动确定发布平台</span>
    </div>

    <!-- 原创声明（所有平台通用） -->
    <div class="original-section">
      <el-checkbox v-model="publish.form.isOriginal" label="声明原创" class="original-checkbox" />
    </div>

    <!-- 视频号专属字段 -->
    <div v-if="isPlatformSelected(2)" class="draft-section">
      <h3>视频号设置</h3>
      <el-checkbox
        v-model="publish.form.isDraft"
        label="仅保存草稿（用手机发布）"
        class="draft-checkbox"
      />
    </div>

    <!-- 抖音专属字段 -->
    <div v-if="isPlatformSelected(3)" class="product-section">
      <h3>抖音商品设置</h3>
      <el-input
        v-model="publish.form.productTitle"
        type="text"
        placeholder="请输入商品名称"
        maxlength="200"
        class="product-name-input"
      />
      <el-input
        v-model="publish.form.productLink"
        type="text"
        placeholder="请输入商品链接"
        maxlength="200"
        class="product-link-input"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { platforms } from '@/composables/publish/usePublishForm'
import { usePublishContext } from '@/composables/publish/publishContext'

const publish = usePublishContext()

// 已选账号对应的平台
const selectedPlatformList = computed(() => {
  return platforms.filter(item => publish.selectedPlatforms.includes(item.key))
})

// 判断某个平台是否已被选中
const isPlatformSelected = (key) => publish.selectedPlatforms.includes(key)
</script>
