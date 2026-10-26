<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import { decideApproval, deleteApproval, fetchApproval, fetchApprovals } from '../api/approvals'

const auth = useAuthStore()

function canDecide(row) {
  if (row.status !== 'pending') return false
  if (auth.role === 'admin') return true
  return row.submitted_by === auth.user?.username
}

const loading = ref(true)
const approvals = ref([])
const activeTab = ref('pending')
const drawerVisible = ref(false)
const current = ref(null)
const comment = ref('')
const submitting = ref(false)

const roleLabels = {
  admin: '管理员',
  procurement: '采购',
  logistics: '物流',
  quality: '质量',
  finance: '财务',
}
const levelText = { CRITICAL: '严重', HIGH: '高', MEDIUM: '中', LOW: '低' }
const levelType = { CRITICAL: 'danger', HIGH: 'danger', MEDIUM: 'warning', LOW: 'success' }
const statusText = { pending: '待处理', approved: '已通过', rejected: '已驳回' }
const statusType = { pending: 'warning', approved: 'success', rejected: 'info' }

function formatTime(value) {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function severityType(severity) {
  if (severity === 'HIGH' || severity === 'CRITICAL') return 'danger'
  return severity === 'MEDIUM' ? 'warning' : 'info'
}

const pendingCount = computed(
  () => approvals.value.filter((item) => item.status === 'pending').length,
)
const filtered = computed(() =>
  approvals.value.filter((item) =>
    activeTab.value === 'pending'
      ? item.status === 'pending'
      : item.status !== 'pending',
  ),
)

async function open(row) {
  comment.value = ''
  drawerVisible.value = true
  current.value = null
  try {
    current.value = await fetchApproval(row.approval_id)
  } catch (error) {
    ElMessage.error('加载详情失败')
    drawerVisible.value = false
  }
}

async function decide(action) {
  if (!current.value) return
  submitting.value = true
  try {
    current.value = await decideApproval(
      current.value.approval_id,
      action,
      comment.value.trim(),
    )
    ElMessage.success(action === 'approve' ? '已通过' : '已驳回')
    await load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail ?? '操作失败')
  } finally {
    submitting.value = false
  }
}

async function load() {
  loading.value = true
  try {
    approvals.value = (await fetchApprovals()).items
  } finally {
    loading.value = false
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      `确定要删除这条审批记录吗？问题：「${row.question.slice(0, 50)}」`,
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await deleteApproval(row.approval_id)
    ElMessage.success('已删除')
    await load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail ?? '删除失败')
  }
}

onMounted(load)
</script>

<template>
  <el-card shadow="never">
    <el-tabs v-model="activeTab">
      <el-tab-pane :label="`待处理 (${pendingCount})`" name="pending" />
      <el-tab-pane label="已处理" name="processed" />
    </el-tabs>

    <el-table v-loading="loading" :data="filtered">
      <el-table-column prop="question" label="问题" min-width="260" />
      <el-table-column label="提交角色" width="100">
        <template #default="{ row }">
          {{ roleLabels[row.submitted_role] ?? row.submitted_role }}
        </template>
      </el-table-column>
      <el-table-column label="风险等级" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="levelType[row.risk_level]">
            {{ levelText[row.risk_level] ?? row.risk_level }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="提交时间" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="statusType[row.status]">
            {{ statusText[row.status] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="130">
        <template #default="{ row }">
          <el-button link type="primary" @click="open(row)">
            {{ canDecide(row) ? '处理' : '查看' }}
          </el-button>
          <el-button
            v-if="row.status !== 'pending'"
            link
            type="danger"
            @click="remove(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-drawer v-model="drawerVisible" title="审批详情" size="520px">
    <template v-if="current">
      <div class="detail-question">{{ current.question }}</div>
      <div class="detail-meta">
        <el-tag size="small" :type="levelType[current.risk_level]">
          风险{{ levelText[current.risk_level] ?? current.risk_level }}
        </el-tag>
        <span>
          {{ roleLabels[current.submitted_role] ?? current.submitted_role }} ·
          {{ formatTime(current.created_at) }}
        </span>
        <el-tag size="small" :type="statusType[current.status]">
          {{ statusText[current.status] }}
        </el-tag>
      </div>

      <div class="section-title">触发原因</div>
      <p class="reason">{{ current.reason || '—' }}</p>

      <div class="section-title">结论</div>
      <p class="conclusion">{{ current.answer || '—' }}</p>
      <div
        v-if="current.decided_by"
        class="decide-meta"
      >
        由 {{ current.decided_by }}
        {{ formatTime(current.decided_at) }}
        {{ current.status === 'approved' ? '通过' : '驳回' }}
      </div>

      <div class="section-title">
        证据链（{{ current.hits.length }} 段文档 + {{ current.graph_paths.length }} 条图谱）
      </div>
      <!-- 文档证据 -->
      <div v-for="(hit, index) in current.hits" :key="'h' + index" class="evidence doc">
        <div class="evidence-tag">
          <el-tag size="small" type="primary" effect="plain">文档</el-tag>
          <span class="evidence-id">[{{ index + 1 }}]</span>
        </div>
        <div class="evidence-source">{{ hit.filename }} · 第 {{ hit.chunk_index + 1 }} 块</div>
        <div class="evidence-fact">{{ hit.text }}</div>
        <div class="evidence-meta">
          <el-tag v-for="role in hit.allowed_roles" :key="role" size="small" effect="plain">
            {{ role }}
          </el-tag>
          <span class="score">相关度 {{ hit.score.toFixed(3) }}</span>
        </div>
      </div>
      <!-- 图谱路径 -->
      <div v-for="(path, index) in current.graph_paths" :key="'g' + index" class="evidence graph">
        <div class="evidence-tag">
          <el-tag size="small" type="success" effect="plain">图谱</el-tag>
          <span class="evidence-id">[G{{ index + 1 }}]</span>
        </div>
        <div class="evidence-source">{{ path.summary }}</div>
        <div class="evidence-meta">
          <el-tag size="small" effect="plain">{{ path.rule_label }}</el-tag>
          <el-tag size="small" effect="plain" :type="severityType(path.severity)">
            {{ path.severity }}
          </el-tag>
          <span>{{ path.hops }} 跳</span>
        </div>
        <div class="evidence-impact">{{ path.reason }}</div>
      </div>
      <div v-if="!current.hits.length && !current.graph_paths.length" class="empty-text">
        无证据
      </div>

      <template v-if="canDecide(current)">
        <div class="section-title">审批意见</div>
        <el-input
          v-model="comment"
          type="textarea"
          :rows="3"
          placeholder="可填写通过/驳回理由（选填），会写入审计"
        />
        <div class="actions">
          <el-button
            type="danger"
            plain
            :loading="submitting"
            @click="decide('reject')"
          >
            驳回
          </el-button>
          <el-button
            type="primary"
            :loading="submitting"
            @click="decide('approve')"
          >
            通过
          </el-button>
        </div>
      </template>
    </template>
  </el-drawer>
</template>

<style scoped>
.detail-question {
  font-size: 16px;
  font-weight: 600;
  line-height: 1.5;
}

.detail-meta {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-top: 10px;
  color: #909399;
  font-size: 12px;
}

.section-title {
  margin: 18px 0 8px;
  color: #909399;
  font-size: 12px;
}

.conclusion {
  margin: 0;
  color: #303133;
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
}

.reason {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
}

.decide-meta {
  margin-top: 8px;
  color: #909399;
  font-size: 12px;
}

.evidence {
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}

.evidence.doc {
  border-left: 3px solid #409eff;
  padding-left: 10px;
}

.evidence.graph {
  border-left: 3px solid #67c23a;
  padding-left: 10px;
}

.evidence-tag {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 4px;
}

.evidence-id {
  color: #909399;
  font-size: 12px;
}

.evidence-source {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.5;
}

.evidence-fact {
  margin-top: 4px;
  color: #606266;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.evidence-impact {
  margin-top: 4px;
  color: #e6a23c;
  font-size: 12px;
  line-height: 1.5;
}

.evidence-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-top: 6px;
  color: #909399;
  font-size: 12px;
}

.score {
  margin-left: auto;
  white-space: nowrap;
}

.empty-text {
  color: #a8abb2;
  font-size: 13px;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}
</style>