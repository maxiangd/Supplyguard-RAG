<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)

const form = reactive({
  username: 'admin',
  password: '',
  tenant: 'demo',
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
</script>

<template>
  <div class="login-page">
    <el-card class="login-card" shadow="always">
      <div class="brand">SupplyGuard</div>
      <div class="subtitle">供应链风险 AgentHarness</div>

      <el-form label-position="top" @submit.prevent="handleLogin">
        <el-form-item label="租户">
          <el-input v-model="form.tenant" placeholder="demo" />
        </el-form-item>
        <el-form-item label="账号">
          <el-input v-model="form.username" placeholder="admin" />
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
  width: 360px;
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
</style>