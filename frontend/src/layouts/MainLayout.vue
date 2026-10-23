<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Odometer,
  ChatDotRound,
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
  { path: '/suppliers', label: '供应商图谱', icon: Share },
  { path: '/review', label: '复核台', icon: Checked },
  { path: '/benchmark', label: 'Benchmark', icon: DataAnalysis },
  { path: '/audit', label: '审计', icon: Document },
  { path: '/admin', label: '管理', icon: Setting },
]

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
        <el-menu-item v-for="menu in menus" :key="menu.path" :index="menu.path">
          <el-icon><component :is="menu.icon" /></el-icon>
          <span>{{ menu.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <span class="title">{{ currentTitle }}</span>
        <div class="header-right">
          <el-tag type="info" effect="plain">{{ auth.tenantId || '未选择租户' }}</el-tag>
          <el-dropdown @command="handleLogout">
            <span class="user">{{ auth.user?.username ?? '未登录' }}</span>
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

.main {
  background: #f5f7fa;
}
</style>
