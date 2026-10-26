<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createUser, deleteUser, fetchUsers, updateUser } from '../api/users'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const loading = ref(true)
const activeTab = ref('users')

const users = ref([])
const roles = ref([])

const userDialog = ref(false)
const userForm = reactive({
  username: '',
  password: '',
  role: 'procurement',
})

const editDialog = ref(false)
const editForm = reactive({
  user_id: '',
  username: '',
  role: 'procurement',
  is_active: true,
})

const isSelf = (user) => user.user_id === auth.user?.user_id

const roleLabels = {
  admin: '管理员',
  procurement: '采购',
  logistics: '物流',
  quality: '质量',
  finance: '财务',
}

// ── 5 角色的真实权限说明（与后端 RBAC 一致，不需要 API）──
const ROLE_POLICIES = [
  {
    name: '管理员 (admin)',
    scope: '全局可见，可管理用户账号、文档权限、审批高风险结论、查看审计日志',
    permissions: ['查看全部文档', '查看全部图谱节点', '管理用户', '审批高风险结论', '查看审计日志', '配置文档可见角色'],
  },
  {
    name: '采购 (procurement)',
    scope: '供应链上游——供应商关系、原料采购、成本与价格风险',
    permissions: ['查看供应商/原料文档', '查看采购相关图谱节点', '提交风险问答', '查看成本分析', '不可见质量召回事件'],
  },
  {
    name: '物流 (logistics)',
    scope: '运输与交付——港口、航线、出口合规与舱位管理',
    permissions: ['查看物流/出口文档', '查看港口/航线图谱节点', '查看替代路径', '不可见供应商详情'],
  },
  {
    name: '质量 (quality)',
    scope: '产品与合规——召回事件、质量追溯、电池法规合规要求',
    permissions: ['查看质量/召回文档', '查看质量事件图谱', '追溯供应商批次', '查看欧盟合规要求'],
  },
  {
    name: '财务 (finance)',
    scope: '成本与结算——采购成本、库存减值、合同条款',
    permissions: ['查看采购/成本文档', '查看价格相关事件', '监控库存减值风险', '不可见港口/航线详情'],
  },
]

async function load() {
  const userList = await fetchUsers()
  users.value = userList
  roles.value = ROLE_POLICIES
  loading.value = false
}

async function addUser() {
  if (!userForm.username || !userForm.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  try {
    const created = await createUser({ ...userForm })
    users.value.push(created)
    userDialog.value = false
    Object.assign(userForm, { username: '', password: '', role: 'procurement' })
    ElMessage.success('用户已创建')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail ?? '创建失败')
  }
}

function openEdit(user) {
  Object.assign(editForm, user)
  editDialog.value = true
}

async function saveEdit() {
  try {
    const updated = await updateUser(editForm.user_id, {
      role: editForm.role,
      is_active: editForm.is_active,
    })
    const target = users.value.find((item) => item.user_id === updated.user_id)
    Object.assign(target, updated)
    editDialog.value = false
    ElMessage.success('用户已更新')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail ?? '更新失败')
  }
}

async function removeUser(user) {
  try {
    await ElMessageBox.confirm(`确定删除账号 ${user.username}？`, '删除用户', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deleteUser(user.user_id)
    users.value = users.value.filter((item) => item.user_id !== user.user_id)
    ElMessage.success('用户已删除')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail ?? '删除失败')
  }
}

onMounted(load)
</script>

<template>
  <el-card v-loading="loading" shadow="never">
    <el-tabs v-model="activeTab">
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
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag
                size="small"
                :type="row.is_active ? 'success' : 'info'"
              >
                {{ row.is_active ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                :disabled="isSelf(row)"
                @click="openEdit(row)"
              >
                编辑
              </el-button>
              <el-button
                link
                type="danger"
                :disabled="isSelf(row)"
                @click="removeUser(row)"
              >
                删除
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
    </el-tabs>
  </el-card>

  <el-dialog v-model="userDialog" title="新建用户" width="420px">
    <el-form label-width="80px">
      <el-form-item label="用户名">
        <el-input v-model="userForm.username" placeholder="登录账号" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input
          v-model="userForm.password"
          type="password"
          show-password
          placeholder="至少 8 位"
        />
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
    </el-form>
    <template #footer>
      <el-button @click="userDialog = false">取消</el-button>
      <el-button type="primary" @click="addUser">创建</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="editDialog" title="编辑用户" width="420px">
    <el-form label-width="80px">
      <el-form-item label="用户名">
        <el-input :model-value="editForm.username" disabled />
      </el-form-item>
      <el-form-item label="角色">
        <el-select v-model="editForm.role" style="width: 100%">
          <el-option
            v-for="(label, value) in roleLabels"
            :key="value"
            :label="label"
            :value="value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-switch
          v-model="editForm.is_active"
          active-text="启用"
          inactive-text="禁用"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="editDialog = false">取消</el-button>
      <el-button type="primary" @click="saveEdit">保存</el-button>
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
