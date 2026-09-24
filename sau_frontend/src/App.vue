<template>
  <div id="app">
    <el-container>
      <el-aside :width="isCollapse ? '64px' : '200px'">
        <div class="sidebar">
          <div class="logo">
            <img v-show="isCollapse" src="/vite.svg" alt="Logo" class="logo-img">
            <h2 v-show="!isCollapse">自媒体自动化运营系统</h2>
          </div>
          <el-menu
            :router="true"
            :default-active="activeMenu"
            :collapse="isCollapse"
            class="sidebar-menu"
            background-color="#001529"
            text-color="#fff"
            active-text-color="#409EFF"
          >
            <el-menu-item index="/">
              <el-icon><HomeFilled /></el-icon>
              <span>首页</span>
            </el-menu-item>
            <el-menu-item index="/account-management">
              <el-icon><User /></el-icon>
              <span>账号管理</span>
            </el-menu-item>
            <el-menu-item index="/material-management">
              <el-icon><Picture /></el-icon>
              <span>素材管理</span>
            </el-menu-item>
            <el-menu-item index="/publish-center">
              <el-icon><Upload /></el-icon>
              <span>发布中心</span>
            </el-menu-item>
            <el-menu-item index="/about">
              <el-icon><DataAnalysis /></el-icon>
              <span>关于</span>
            </el-menu-item>
          </el-menu>
        </div>
      </el-aside>
      <el-container>
        <el-header>
          <div class="header-content">
            <div class="header-left">
              <el-icon class="toggle-sidebar" @click="toggleSidebar"><Fold /></el-icon>
              <span class="page-title">{{ currentTitle }}</span>
            </div>
            <div class="header-right">
              <span class="file-path">{{ currentFilePath }}</span>
              <el-icon class="copy-icon" @click="copyFilePath" title="复制路径 (Ctrl+Shift+Alt+C)"><DocumentCopy /></el-icon>
            </div>
          </div>
        </el-header>
        <el-main>
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  HomeFilled, User, DataAnalysis,
  Fold, Picture, Upload
} from '@element-plus/icons-vue'

const route = useRoute()

// 当前激活的菜单项
const activeMenu = computed(() => {
  return route.path
})

// 当前页面对应的源文件路径
const currentFilePath = computed(() => {
  return route.meta?.filePath || ''
})

// 当前页面标题
const currentTitle = computed(() => {
  return route.meta?.title || ''
})

// 侧边栏折叠状态
const isCollapse = ref(false)

// 切换侧边栏折叠状态
const toggleSidebar = () => {
  isCollapse.value = !isCollapse.value
}

// 复制当前文件路径到剪贴板
const copyFilePath = async () => {
  const path = currentFilePath.value
  if (!path) {
    ElMessage.warning('当前页面未配置源文件路径')
    return
  }
  try {
    await navigator.clipboard.writeText(path)
    ElMessage.success(`已复制：${path}`)
  } catch (e) {
    // fallback
    const ta = document.createElement('textarea')
    ta.value = path
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    ElMessage.success(`已复制：${path}`)
  }
}

// 全局快捷键：Ctrl+Shift+Alt+C
const handleKeydown = (e) => {
  if (e.ctrlKey && e.shiftKey && e.altKey && e.key.toLowerCase() === 'c') {
    e.preventDefault()
    copyFilePath()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

#app {
  min-height: 100vh;
}

.el-container {
  height: 100vh;
}

.el-aside {
  background-color: #001529;
  color: #fff;
  height: 100vh;
  overflow: hidden;
  transition: width 0.3s;
  
  .sidebar {
    display: flex;
    flex-direction: column;
    height: 100%;
    
    .logo {
      height: 60px;
      padding: 0 16px;
      display: flex;
      align-items: center;
      background-color: #002140;
      overflow: hidden;
      
      .logo-img {
        width: 32px;
        height: 32px;
        margin-right: 12px;
      }
      
      h2 {
        color: #fff;
        font-size: 16px;
        font-weight: 600;
        white-space: nowrap;
        margin: 0;
      }
    }
    
    .sidebar-menu {
      border-right: none;
      flex: 1;
      
      .el-menu-item {
        display: flex;
        align-items: center;
        
        .el-icon {
          margin-right: 10px;
          font-size: 18px;
        }
      }
    }
  }
}

.el-header {
  background-color: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding: 0;
  height: 60px;
  
  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    height: 100%;
    padding: 0 16px;
    
    .header-left {
      display: flex;
      align-items: center;
      gap: 12px;

      .toggle-sidebar {
        font-size: 20px;
        cursor: pointer;
        color: var(--el-text-color-regular);
        
        &:hover {
          color: var(--el-color-primary);
        }
      }

      .page-title {
        font-size: 16px;
        font-weight: 600;
        color: var(--el-text-color-primary);
      }
    }
    
    .header-right {
      display: flex;
      align-items: center;
      gap: 8px;

      .file-path {
        font-size: 12px;
        font-family: 'Consolas', 'Monaco', monospace;
        color: var(--el-text-color-secondary);
        max-width: 360px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .copy-icon {
        font-size: 16px;
        color: var(--el-text-color-secondary);
        cursor: pointer;
        transition: color 0.2s;

        &:hover {
          color: var(--el-color-primary);
        }
      }

      .user-dropdown {
        display: flex;
        align-items: center;
        cursor: pointer;
        
        .username {
          margin: 0 8px;
          color: var(--el-text-color-regular);
        }
        
        .el-icon {
          font-size: 12px;
          color: var(--el-text-color-secondary);
        }
      }
    }
  }
}

.el-main {
  background-color: var(--el-bg-color-page);
  padding: 20px;
  overflow-y: auto;
}
</style>
