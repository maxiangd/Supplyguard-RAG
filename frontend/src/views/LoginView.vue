<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)

const demoAccounts = [
  { username: 'catl_admin', label: '管理员' },
  { username: 'catl_procurement', label: '采购' },
  { username: 'catl_logistics', label: '物流' },
  { username: 'catl_quality', label: '质量' },
  { username: 'catl_finance', label: '财务' },
]

const form = reactive({
  username: 'catl_procurement',
  password: 'catl123',
})

async function handleLogin() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入账号和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(form)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (error) {
    const detail = error.response?.data?.detail
    ElMessage.error(typeof detail === 'string' ? detail : '登录失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

function quickLogin(account) {
  form.username = account.username
  form.password = 'catl123'
  handleLogin()
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card" shadow="always">
      <div class="brand">SupplyGuard</div>
      <div class="subtitle">宁德时代供应链 · 风险 AgentHarness</div>

      <el-form label-position="top" @submit.prevent="handleLogin">
        <el-form-item label="账号">
          <el-input v-model="form.username" placeholder="请输入账号" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="请输入密码"
          />
        </el-form-item>
        <el-button
          type="primary"
          class="login-btn"
          :loading="loading"
          @click="handleLogin"
        >
          登录
        </el-button>
      </el-form>

      <div class="quick">
        <div class="quick-title">演示账号快捷登录（密码 catl123）</div>
        <div class="quick-buttons">
          <el-button
            v-for="account in demoAccounts"
            :key="account.username"
            size="small"
            @click="quickLogin(account)"
          >
            {{ account.label }}
          </el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: linear-gradient(135deg, #001529 0%, #1677ff 100%);
}

.login-card {
  width: 380px;
  padding: 8px 12px;
}

.brand {
  font-size: 22px;
  font-weight: 700;
  text-align: center;
}

.subtitle {
  margin: 6px 0 24px;
  color: #909399;
  font-size: 13px;
  text-align: center;
}

.login-btn {
  width: 100%;
}

.quick {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.quick-title {
  margin-bottom: 10px;
  color: #909399;
  font-size: 12px;
  text-align: center;
}

.quick-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.quick-buttons .el-button {
  margin-left: 0;
}
</style>