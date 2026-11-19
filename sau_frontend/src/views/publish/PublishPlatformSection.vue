<template>
  <div class="platform-section">
    <h3>平台</h3>
    <el-radio-group v-model="tab.selectedPlatform" class="platform-radios">
      <el-radio
        v-for="platform in platforms"
        :key="platform.key"
        :label="platform.key"
        class="platform-radio"
      >
        {{ platform.name }}
      </el-radio>
    </el-radio-group>
  </div>

  <!-- 原创声明 -->
  <div class="original-section">
    <el-checkbox v-model="tab.isOriginal" label="声明原创" class="original-checkbox" />
  </div>

  <!-- 草稿选项 (仅在视频号可见) -->
  <div v-if="tab.selectedPlatform === 2" class="draft-section">
    <el-checkbox
      v-model="tab.isDraft"
      label="视频号仅保存草稿(用手机发布)"
      class="draft-checkbox"
    />
  </div>

  <!-- 商品链接 (仅在抖音可见) -->
  <div v-if="tab.selectedPlatform === 3" class="product-section">
    <h3>商品链接</h3>
    <el-input
      v-model="tab.productTitle"
      type="text"
      :rows="1"
      placeholder="请输入商品名称"
      maxlength="200"
      class="product-name-input"
    />
    <el-input
      v-model="tab.productLink"
      type="text"
      :rows="1"
      placeholder="请输入商品链接"
      maxlength="200"
      class="product-link-input"
    />
  </div>
</template>

<script setup>
import { platforms } from '@/composables/publish/usePublishTabs'

defineProps({
  tab: {
    type: Object,
    required: true
  }
})
</script>
