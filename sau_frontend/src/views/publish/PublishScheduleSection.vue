<template>
  <div class="schedule-section">
    <h3>定时发布</h3>
    <div class="schedule-controls">
      <el-switch
        v-model="publish.form.scheduleEnabled"
        active-text="定时发布"
        inactive-text="立即发布"
      />
      <div v-if="publish.form.scheduleEnabled" class="schedule-settings">
        <div class="schedule-item">
          <span class="label">每天发布视频数：</span>
          <el-select v-model="publish.form.videosPerDay" placeholder="选择发布数量">
            <el-option v-for="num in 55" :key="num" :label="num" :value="num" />
          </el-select>
        </div>
        <div class="schedule-item">
          <span class="label">每天发布时间：</span>
          <el-time-select
            v-for="(time, index) in publish.form.dailyTimes"
            :key="index"
            v-model="publish.form.dailyTimes[index]"
            start="00:00"
            step="00:30"
            end="23:30"
            placeholder="选择时间"
          />
          <el-button
            v-if="publish.form.dailyTimes.length < publish.form.videosPerDay"
            type="primary"
            size="small"
            @click="publish.form.dailyTimes.push('10:00')"
          >
            添加时间
          </el-button>
        </div>
        <div class="schedule-item">
          <span class="label">开始天数：</span>
          <el-select v-model="publish.form.startDays" placeholder="选择开始天数">
            <el-option :label="'明天'" :value="0" />
            <el-option :label="'后天'" :value="1" />
          </el-select>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { usePublishContext } from '@/composables/publish/publishContext'

const publish = usePublishContext()
</script>
