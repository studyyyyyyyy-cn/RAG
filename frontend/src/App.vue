<template>
  <el-config-provider :locale="zhCn" :dialog="{ lockScroll: false }">
    <el-container class="app-shell">
      <el-header class="app-topbar">
        <div class="logo">
          <div class="logo-mark">
            <el-icon :size="22"><DataAnalysis /></el-icon>
          </div>
          <div>
            <div class="logo-title">RAG知识库管理及问答系统</div>
            <div class="logo-subtitle">RAG Knowledge OS</div>
          </div>
        </div>

        <el-menu :default-active="activeMenu" router class="sidebar-menu">
          <el-menu-item index="/dashboard">
            <el-icon><DataLine /></el-icon>
            <span>数据看板</span>
          </el-menu-item>
          <el-menu-item index="/knowledge">
            <el-icon><Collection /></el-icon>
            <span>知识库管理</span>
          </el-menu-item>
          <el-menu-item index="/chat">
            <el-icon><ChatDotRound /></el-icon>
            <span>智能问答</span>
          </el-menu-item>
          <el-menu-item index="/shortcuts">
            <el-icon><Star /></el-icon>
            <span>快捷方式</span>
          </el-menu-item>
          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon>
            <span>系统设置</span>
          </el-menu-item>
          <el-menu-item index="/mcp-test">
            <el-icon><Connection /></el-icon>
            <span>MCP 测试</span>
          </el-menu-item>
          <el-menu-item index="/api-test">
            <el-icon><DocumentChecked /></el-icon>
            <span>API 测试</span>
          </el-menu-item>
        </el-menu>
      </el-header>

      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-config-provider>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

const route = useRoute()
const activeMenu = computed(() => route.path)
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}

.app-shell {
  height: 100vh;
  padding: 16px;
  gap: 16px;
  background: transparent;
  flex-direction: column;
}

.app-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  height: auto;
  padding: 14px 18px;
  border-radius: 30px;
  background:
    radial-gradient(circle at top left, rgba(255, 107, 107, 0.14), transparent 24%),
    linear-gradient(180deg, #1f2742 0%, #26294e 48%, #1f3551 100%);
  color: #fff;
  box-shadow: 0 24px 60px rgba(30, 42, 81, 0.28);
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px 18px;
}

.logo-mark {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 18px;
  background: linear-gradient(135deg, #ff7a59, #48dbfb 60%, #1dd1a1);
  color: #fff;
  box-shadow: 0 14px 30px rgba(79, 124, 255, 0.24);
}

.logo-title {
  font-size: 20px;
  font-weight: 800;
}

.logo-subtitle {
  margin-top: 3px;
  color: rgba(234, 238, 255, 0.62);
  font-size: 12px;
}

.sidebar-menu {
  border-right: 0 !important;
  background: transparent !important;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.sidebar-menu .el-menu-item {
  height: 46px;
  margin-bottom: 0;
  border-radius: 18px;
  color: rgba(223, 229, 255, 0.78);
}

.sidebar-menu .el-menu-item:hover {
  background: rgba(255, 255, 255, 0.08) !important;
}

.sidebar-menu .el-menu-item.is-active {
  color: #fff !important;
  background: linear-gradient(135deg, rgba(79, 124, 255, 0.36), rgba(72, 219, 251, 0.22)) !important;
  box-shadow: inset 0 0 0 1px rgba(140, 191, 255, 0.18);
}

.app-main {
  border-radius: 34px;
  overflow-y: auto;
  background: transparent;
  padding: 0 !important;
  min-height: 0;
  flex: 1;
}

@media (max-width: 1100px) {
  .app-shell {
    padding: 10px;
    gap: 10px;
  }

  .app-topbar {
    flex-direction: column;
    align-items: stretch;
  }

  .sidebar-menu {
    justify-content: flex-start;
  }
}
</style>
