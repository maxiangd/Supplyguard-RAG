<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createTenant, createUser, fetchAdminData } from '../api/mock'

const loading = ref(true)
const activeTab = ref('tenants')

const tenants = ref([])
const users = ref([])
const roles = ref([])
const metrics = ref({})
const logs = ref([])

const tenantDialog = ref(false)
const tenantForm = reactive({ tenant_id: '', name: '' })
const userDialog = ref(false)
const userForm = reactive({
  username: '',
  role: 'procurement',
  tenant_id: 'demo',
})

const roleLabels = {
  admin: '管理员',
  procurement: '采购',
  logistics: '物流',
  quality: '质量',
  finance: '财务',
}
const logType = { INFO: 'info', WARNING: 'warning', ERROR: 'danger' }

async function load() {
  const data = await fetchAdminData()
  tenants.value = data.tenants
  users.value = data.users
  roles.value = data.roles
  metrics.value = data.metrics
  logs.value = data.logs
  loading.value = false
}

async function addTenant() {
  if (!tenantForm.tenant_id || !tenantForm.name) {
    ElMessage.warning('请填写租户 ID 和名称')
    return
  }
  const created = await createTenant({ ...tenantForm })
  tenants.value.push(created)
  tenantDialog.value = false
  Object.assign(tenantForm, { tenant_id: '', name: '' })
  ElMessage.success('租户已创建')
}

async function addUser() {
  if (!userForm.username) {
    ElMessage.warning('请填写用户名')
    return
  }
  const created = await createUser({ ...userForm })
  users.value.push(created)
  userDialog.value = false
  Object.assign(userForm, { username: '', role: 'procurement', tenant_id: 'demo' })
  ElMessage.success('用户已创建')
}

function toggleUser(user) {
  user.status = user.status === 'active' ? 'disabled' : 'active'
  ElMessage.success(
    user.status === 'active' ? `已启用 ${user.username}` : `已禁用 ${user.username}`,
  )
}

onMounted(load)
</script>

<template>
  <el-card v-loading="loading" shadow="never">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="租户" name="tenants">
        <div class="toolbar">
          <el-button type="primary" @click="tenantDialog = true">
            新建租户
          </el-button>
        </div>
        <el-table :data="tenants" size="small">
          <el-table-column prop="tenant_id" label="租户 ID" width="140" />
          <el-table-column prop="name" label="名称" min-width="180" />
          <el-table-column prop="created_at" label="创建时间" width="140" />
          <el-table-column prop="user_count" label="用户数" width="90" />
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="用户" name="users">
        <div class="toolbar">
          <el-button type="primary" @click="userDialog = true">
            新建用户
          </el-button>
        </div>
        <el-table :data="users" size="small">
          <el-table-column prop="username" label="用户名" width="140" />
          <el-table-column label="角色" width="110">
            <template #default="{ row }">
              {{ roleLabels[row.role] ?? row.role }}
            </template>
          </el-table-column>
          <el-table-column prop="tenant_id" label="租户" width="120" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag
                size="small"
                :type="row.status === 'active' ? 'success' : 'info'"
              >
                {{ row.status === 'active' ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button link type="primary" @click="toggleUser(row)">
                {{ row.status === 'active' ? '禁用' : '启用' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="角色与策略" name="roles">
        <el-table :data="roles" size="small">
          <el-table-column label="角色" width="110">
            <template #default="{ row }">{{ row.name }}</template>
          </el-table-column>
          <el-table-column prop="scope" label="职责范围" min-width="260" />
          <el-table-column label="权限" min-width="260">
            <template #default="{ row }">
              <el-tag
                v-for="permission in row.permissions"
                :key="permission"
                size="small"
                effect="plain"
                class="tag"
              >
                {{ permission }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="监控" name="monitor">
        <el-row :gutter="16">
          <el-col :span="6">
            <el-card shadow="never">
              <div class="stat-label">今日请求</div>
              <div class="stat-value">{{ metrics.requests_today }}</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="never">
              <div class="stat-label">LLM 调用</div>
              <div class="stat-value">{{ metrics.llm_calls }}</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="never">
              <div class="stat-label">越权拦截</div>
              <div class="stat-value">{{ metrics.blocked }}</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="never">
              <div class="stat-label">审批积压</div>
              <div class="stat-value">{{ metrics.approval_backlog }}</div>
            </el-card>
          </el-col>
        </el-row>

        <el-table :data="logs" size="small" class="logs">
          <el-table-column prop="time" label="时间" width="100" />
          <el-table-column label="级别" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="logType[row.level]">
                {{ row.level }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="message" label="日志" min-width="300" />
          <el-table-column prop="request_id" label="request_id" width="140" />
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </el-card>

  <el-dialog v-model="tenantDialog" title="新建租户" width="420px">
    <el-form label-width="80px">
      <el-form-item label="租户 ID">
        <el-input v-model="tenantForm.tenant_id" placeholder="例如 acme" />
      </el-form-item>
      <el-form-item label="名称">
        <el-input v-model="tenantForm.name" placeholder="例如 Acme 供应链" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="tenantDialog = false">取消</el-button>
      <el-button type="primary" @click="addTenant">创建</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="userDialog" title="新建用户" width="420px">
    <el-form label-width="80px">
      <el-form-item label="用户名">
        <el-input v-model="userForm.username" placeholder="登录账号" />
      </el-form-item>
      <el-form-item label="角色">
        <el-select v-model="userForm.role" style="width: 100%">
          <el-option
            v-for="(label, value) in roleLabels"
            :key="value"
            :label="label"
            :value="value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="租户">
        <el-select v-model="userForm.tenant_id" style="width: 100%">
          <el-option
            v-for="tenant in tenants"
            :key="tenant.tenant_id"
            :label="`${tenant.name}（${tenant.tenant_id}）`"
            :value="tenant.tenant_id"
          />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="userDialog = false">取消</el-button>
      <el-button type="primary" @click="addUser">创建</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.toolbar {
  margin-bottom: 12px;
}

.tag {
  margin-right: 6px;
}

.stat-label {
  color: #909399;
  font-size: 13px;
}

.stat-value {
  margin-top: 6px;
  font-size: 26px;
  font-weight: 600;
}

.logs {
  margin-top: 16px;
}
</style>
