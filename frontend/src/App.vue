<template>
  <el-config-provider :locale="zhCn">
    <div class="app-root">
      <!-- Sidebar -->
      <aside class="sidebar">
        <div class="sidebar-brand">
          <div class="brand-icon">
            <el-icon :size="24"><Cpu /></el-icon>
          </div>
          <div class="brand-text">
            <div class="brand-title">RAG Pro</div>
            <div class="brand-sub">Knowledge OS</div>
          </div>
        </div>

        <el-menu :default-active="activeMenu" router class="nav-menu">
          <el-menu-item index="/dashboard">
            <el-icon><Odometer /></el-icon>
            <span>数据看板</span>
          </el-menu-item>
          <el-menu-item index="/knowledge">
            <el-icon><FolderOpened /></el-icon>
            <span>知识库</span>
          </el-menu-item>
          <el-menu-item index="/chat">
            <el-icon><ChatLineSquare /></el-icon>
            <span>智能问答</span>
          </el-menu-item>
          <el-menu-item index="/knowledge-graph">
            <el-icon><Share /></el-icon>
            <span>知识图谱</span>
          </el-menu-item>
          <el-menu-item index="/vector-status">
            <el-icon><Monitor /></el-icon>
            <span>向量状态</span>
          </el-menu-item>
          <el-menu-item index="/shortcuts">
            <el-icon><Star /></el-icon>
            <span>快捷方式</span>
          </el-menu-item>

          <div class="nav-divider"></div>

          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon>
            <span>系统设置</span>
          </el-menu-item>
          <el-menu-item index="/mcp-test">
            <el-icon><Connection /></el-icon>
            <span>MCP</span>
          </el-menu-item>
          <el-menu-item index="/api-test">
            <el-icon><Document /></el-icon>
            <span>API</span>
          </el-menu-item>
        </el-menu>

        <div class="sidebar-footer">
          <el-tag size="small" type="info" effect="plain">v2.1</el-tag>
        </div>
      </aside>

      <!-- Main -->
      <main class="main-area">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
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
/* ── Global Reset ── */
*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

html, body, #app {
  height: 100%;
  font-family: "Inter", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #f0f2f5;
  color: #1a1a2e;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-thumb { background: #c0c4cc; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #909399; }

/* ── Transition ── */
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>

<style scoped>
.app-root {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* ── Sidebar ── */
.sidebar {
  width: 230px;
  min-width: 230px;
  background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 24px 20px 20px;
}

.brand-icon {
  width: 44px; height: 44px;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 14px;
  color: #fff;
  box-shadow: 0 8px 20px rgba(102, 126, 234, 0.35);
}

.brand-title {
  font-size: 18px; font-weight: 700; color: #fff; letter-spacing: -0.3px;
}

.brand-sub {
  font-size: 11px; color: rgba(255,255,255,0.45); margin-top: 2px;
}

/* ── Nav Menu ── */
.nav-menu {
  flex: 1;
  border-right: 0 !important;
  background: transparent !important;
  padding: 8px 12px;
  overflow-y: auto;
}

.nav-menu .el-menu-item {
  height: 42px; line-height: 42px;
  margin-bottom: 2px;
  border-radius: 10px;
  color: rgba(255, 255, 255, 0.65);
  font-size: 14px;
  transition: all 0.2s;
}

.nav-menu .el-menu-item:hover {
  background: rgba(255, 255, 255, 0.06) !important;
  color: #fff !important;
}

.nav-menu .el-menu-item.is-active {
  color: #fff !important;
  background: rgba(102, 126, 234, 0.25) !important;
  font-weight: 600;
}

.nav-divider {
  height: 1px;
  background: rgba(255,255,255,0.08);
  margin: 12px 8px;
}

/* ── Sidebar Footer ── */
.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(255,255,255,0.06);
}

/* ── Main ── */
.main-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: #f0f2f5;
}
</style>
