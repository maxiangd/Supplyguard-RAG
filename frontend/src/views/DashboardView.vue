<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchDashboard } from '../api/dashboard'

const router = useRouter()
const loading = ref(true)
const data = ref({
  stats: [],
  highRiskSuppliers: [],
  recentEvents: [],
  pendingReviews: [],
})

const levelText = { high: '高', medium: '中', low: '低' }
const levelType = { high: 'danger', medium: 'warning', low: 'success' }

onMounted(async () => {
  data.value = await fetchDashboard()
  loading.value = false
})
</script>

<template>
  <div v-loading="loading">
    <el-row :gutter="16">
      <el-col v-for="stat in data.stats" :key="stat.key" :span="6">
        <el-card shadow="never">
          <div class="stat-label">{{ stat.label }}</div>
          <div class="stat-value" :style="{ color: stat.color }">
            {{ stat.value }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="row">
      <el-col :span="16">
        <el-card shadow="never">
          <template #header>
            <span>高风险供应商</span>
          </template>
          <el-table :data="data.highRiskSuppliers" size="small">
            <el-table-column prop="name" label="供应商" min-width="140" />
            <el-table-column prop="region" label="区域" width="90" />
            <el-table-column label="风险等级" width="90">
              <template #default="{ row }">
                <el-tag :type="levelType[row.risk_level]" size="small">
                  {{ levelText[row.risk_level] }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="风险分" width="140">
              <template #default="{ row }">
                <el-progress
                  :percentage="row.score"
                  :color="row.score >= 80 ? '#f56c6c' : '#e6a23c'"
                />
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="主要原因" min-width="160" />
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="never" class="pending">
          <template #header>
            <span>待复核结论</span>
          </template>
          <div
            v-for="item in data.pendingReviews"
            :key="item.review_id"
            class="pending-item"
          >
            <div class="pending-question">{{ item.question }}</div>
            <div class="pending-meta">
              {{ item.requested_by }} · {{ item.created_at }}
            </div>
          </div>
          <el-button
            v-if="data.pendingReviews.length"
            type="primary"
            link
            @click="router.push('/review')"
          >
            去复核台处理 →
          </el-button>
          <el-empty
            v-else
            :image-size="60"
            description="暂无待复核结论"
          />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="row">
      <template #header>
        <span>最近风险事件</span>
      </template>
      <el-table :data="data.recentEvents" size="small">
        <el-table-column prop="time" label="时间" width="150" />
        <el-table-column prop="title" label="事件" min-width="200" />
        <el-table-column prop="type" label="类型" width="90" />
        <el-table-column label="等级" width="80">
          <template #default="{ row }">
            <el-tag :type="levelType[row.level]" size="small">
              {{ levelText[row.level] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="affected" label="影响供应商" width="110" />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.stat-label {
  color: #909399;
  font-size: 13px;
}

.stat-value {
  margin-top: 8px;
  font-size: 28px;
  font-weight: 600;
}

.row {
  margin-top: 16px;
}

.pending-item {
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}

.pending-question {
  font-size: 14px;
}

.pending-meta {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
}

.pending :deep(.el-card__body) {
  padding-top: 4px;
}
</style>