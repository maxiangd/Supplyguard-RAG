// 路由配置：把「浏览器地址栏的路径」映射到「要显示的页面组件」。
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue') },
  {
    path: '/',
    component: () => import('../layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'dashboard', component: () => import('../views/DashboardView.vue') },
      { path: 'chat', name: 'chat', component: () => import('../views/ChatView.vue') },
      { path: 'suppliers', name: 'suppliers', component: () => import('../views/SuppliersView.vue') },
      { path: 'review', name: 'review', component: () => import('../views/ReviewView.vue') },
      { path: 'benchmark', name: 'benchmark', component: () => import('../views/BenchmarkView.vue') },
      { path: 'audit', name: 'audit', component: () => import('../views/AuditView.vue') },
      { path: 'admin', name: 'admin', component: () => import('../views/AdminView.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.name !== 'login' && !auth.isLoggedIn) {
    return { name: 'login' }
  }
  if (to.name === 'login' && auth.isLoggedIn) {
    return { name: 'dashboard' }
  }
})

export default router
