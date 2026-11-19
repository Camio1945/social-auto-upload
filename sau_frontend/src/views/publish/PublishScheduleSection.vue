<template>
  <div class="schedule-section">
    <h3>定时发布</h3>
    <div class="schedule-controls">
      <el-switch
        v-model="tab.scheduleEnabled"
        active-text="定时发布"
        inactive-text="立即发布"
      />
      <div v-if="tab.scheduleEnabled" class="schedule-settings">
        <div class="schedule-item">
          <span class="label">每天发布视频数：</span>
          <el-select v-model="tab.videosPerDay" placeholder="选择发布数量">
            <el-option v-for="num in 55" :key="num" :label="num" :value="num" />
          </el-select>
        </div>
        <div class="schedule-item">
          <span class="label">每天发布时间：</span>
          <el-time-select
            v-for="(time, index) in tab.dailyTimes"
            :key="index"
            v-model="tab.dailyTimes[index]"
            start="00:00"
            step="00:30"
            end="23:30"
            placeholder="选择时间"
          />
          <el-button
            v-if="tab.dailyTimes.length < tab.videosPerDay"
            type="primary"
            size="small"
            @click="tab.dailyTimes.push('10:00')"
          >
            添加时间
          </el-button>
        </div>
        <div class="schedule-item">
          <span class="label">开始天数：</span>
          <el-select v-model="tab.startDays" placeholder="选择开始天数">
            <el-option :label="'明天'" :value="0" />
            <el-option :label="'后天'" :value="1" />
          </el-select>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  tab: {
    type: Object,
    required: true
  }
})
</script>
