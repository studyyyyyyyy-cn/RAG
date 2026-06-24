import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    path: '/knowledge',
    name: 'KnowledgeBase',
    component: () => import('@/views/KnowledgeBase.vue'),
  },
  {
    path: '/knowledge/:id/documents',
    name: 'DocumentManager',
    component: () => import('@/views/DocumentManager.vue'),
  },
  {
    path: '/kb/:id/test-chat',
    name: 'DocumentTestChat',
    component: () => import('@/views/DocumentTestChat.vue'),
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('@/views/Chat.vue'),
  },
  {
    path: '/shortcuts',
    name: 'Shortcuts',
    component: () => import('@/views/Shortcuts.vue'),
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue'),
  },
  {
    path: '/mcp-test',
    name: 'McpTest',
    component: () => import('@/views/McpTest.vue'),
  },
  {
    path: '/api-test',
    name: 'ApiTest',
    component: () => import('@/views/ApiTest.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
