<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Odometer,
  ChatDotRound,
  FolderOpened,
  Share,
  Checked,
  DataAnalysis,
  Document,
  Setting,
} from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const menus = [
  { path: '/dashboard', label: '风险看板', icon: Odometer },
  { path: '/chat', label: '风险问答', icon: ChatDotRound },
  { path: '/documents', label: '文档库', icon: FolderOpened },
  { path: '/suppliers', label: '供应商图谱', icon: Share },
  { path: '/review', label: '复核台', icon: Checked },
  { path: '/benchmark', label: 'Benchmark', icon: DataAnalysis, roles: ['admin'] },
  { path: '/audit', label: '审计', icon: Document, roles: ['admin'] },
  { path: '/admin', label: '管理', icon: Setting, roles: ['admin'] },
]

const roleLabels = {
  admin: '管理员',
  procurement: '采购',
  logistics: '物流',
  quality: '质量',
  finance: '财务',
}

const visibleMenus = computed(() =>
  menus.filter((menu) => !menu.roles || menu.roles.includes(auth.role)),
)
const activeMenu = computed(() => route.path)
const currentTitle = computed(
  () => menus.find((menu) => menu.path === route.path)?.label ?? '',
)

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">SupplyGuard</div>
      <el-menu :default-active="activeMenu" router class="menu">
        <el-menu-item v-for="menu in visibleMenus" :key="menu.path" :index="menu.path">
          <el-icon><component :is="menu.icon" /></el-icon>
          <span>{{ menu.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <span class="title">{{ currentTitle }}</span>
        <div class="header-right">
          <span class="company">宁德时代供应链</span>
          <el-dropdown @command="handleLogout">
            <span class="user">
              {{ auth.user?.username ?? '未登录' }}
              <span class="role">{{ roleLabels[auth.role] ?? '' }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100vh;
}

.aside {
  background: #001529;
}

.logo {
  height: 56px;
  line-height: 56px;
  text-align: center;
  color: #fff;
  font-weight: 600;
  letter-spacing: 1px;
}

.menu {
  border-right: none;
  background: transparent;
}

.menu :deep(.el-menu-item) {
  color: rgba(255, 255, 255, 0.75);
}

.menu :deep(.el-menu-item.is-active) {
  color: #fff;
  background: #1677ff;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e4e7ed;
  background: #fff;
}

.title {
  font-size: 16px;
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user {
  cursor: pointer;
  color: #303133;
}

.role {
  margin-left: 6px;
  color: #909399;
  font-size: 12px;
}

.company {
  color: #606266;
  font-size: 13px;
}

.main {
  background: #f5f7fa;
}
</style>
