<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchReviews, submitReview } from '../api/mock'

const loading = ref(true)
const reviews = ref([])
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
const levelText = { high: '高', medium: '中', low: '低' }
const levelType = { high: 'danger', medium: 'warning', low: 'success' }
const statusText = { pending: '待处理', approved: '已通过', rejected: '已驳回' }
const statusType = { pending: 'warning', approved: 'success', rejected: 'info' }

const pendingCount = computed(
  () => reviews.value.filter((item) => item.status === 'pending').length,
)
const filtered = computed(() =>
  reviews.value.filter((item) =>
    activeTab.value === 'pending'
      ? item.status === 'pending'
      : item.status !== 'pending',
  ),
)

function open(row) {
  current.value = row
  comment.value = ''
  drawerVisible.value = true
}

async function decide(action) {
  if (!current.value) return
  submitting.value = true
  try {
    await submitReview({
      review_id: current.value.review_id,
      action,
      comment: comment.value,
    })
    const target = reviews.value.find(
      (item) => item.review_id === current.value.review_id,
    )
    if (target) {
      target.status = action === 'approve' ? 'approved' : 'rejected'
    }
    ElMessage.success(
      action === 'approve' ? '已通过，工作流恢复执行' : '已驳回，已通知提交人',
    )
    drawerVisible.value = false
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  reviews.value = await fetchReviews()
  loading.value = false
})
</script>

<template>
  <el-card shadow="never">
    <el-tabs v-model="activeTab">
      <el-tab-pane :label="`待处理 (${pendingCount})`" name="pending" />
      <el-tab-pane label="已处理" name="processed" />
    </el-tabs>

    <el-table v-loading="loading" :data="filtered">
      <el-table-column prop="question" label="复核事项" min-width="260" />
      <el-table-column label="提交角色" width="100">
        <template #default="{ row }">
          {{ roleLabels[row.requested_by] ?? row.requested_by }}
        </template>
      </el-table-column>
      <el-table-column label="风险等级" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="levelType[row.risk_level]">
            {{ levelText[row.risk_level] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="提交时间" width="150" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="statusType[row.status]">
            {{ statusText[row.status] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90">
        <template #default="{ row }">
          <el-button link type="primary" @click="open(row)">
            {{ row.status === 'pending' ? '处理' : '查看' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-drawer v-model="drawerVisible" title="复核详情" size="480px">
    <template v-if="current">
      <div class="detail-question">{{ current.question }}</div>
      <div class="detail-meta">
        <el-tag size="small" :type="levelType[current.risk_level]">
          风险{{ levelText[current.risk_level] }}
        </el-tag>
        <span>
          {{ roleLabels[current.requested_by] ?? current.requested_by }} ·
          {{ current.created_at }}
        </span>
      </div>

      <div class="section-title">结论</div>
      <p class="conclusion">{{ current.conclusion }}</p>

      <div class="section-title">证据</div>
      <div v-for="citation in current.citations" :key="citation.id" class="citation">
        <div class="citation-title">[{{ citation.id }}] {{ citation.title }}</div>
        <div class="citation-snippet">{{ citation.snippet }}</div>
      </div>
      <div v-if="!current.citations.length" class="empty-text">无附加证据</div>

      <template v-if="current.graph_paths.length">
        <div class="section-title">图谱路径</div>
        <div
          v-for="(path, index) in current.graph_paths"
          :key="index"
          class="path"
        >
          {{ path.nodes.join(' → ') }}（{{ path.relation }}）
        </div>
      </template>

      <template v-if="current.status === 'pending'">
        <div class="section-title">复核意见</div>
        <el-input
          v-model="comment"
          type="textarea"
          :rows="3"
          placeholder="可填写通过/驳回理由（选填）"
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
}

.citation {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.citation-title {
  font-size: 13px;
  font-weight: 600;
}

.citation-snippet {
  margin-top: 4px;
  color: #606266;
  font-size: 12px;
  line-height: 1.6;
}

.path {
  padding: 6px 0;
  font-size: 13px;
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
