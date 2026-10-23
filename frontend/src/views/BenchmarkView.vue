<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchBenchmark, runBenchmark } from '../api/mock'

const loading = ref(true)
const running = ref(false)
const cases = ref([])
const run = ref(null)
const activeTab = ref('cases')

const metricDefs = [
  { key: 'f1', label: 'F1' },
  { key: 'path_hit_rate', label: '图谱路径命中率' },
  { key: 'role_block_rate', label: '越权拦截率' },
  { key: 'risk_accuracy', label: '风险等级准确率' },
  { key: 'precision', label: 'Precision' },
  { key: 'recall', label: 'Recall' },
]

function pct(value) {
  return `${Math.round(value * 100)}%`
}

function delta(current, baseline) {
  const diff = Math.round((current - baseline) * 100)
  return `${diff >= 0 ? '+' : ''}${diff} pt`
}

const cards = computed(() => {
  if (!run.value) return []
  return metricDefs.slice(0, 4).map((def) => ({
    key: def.key,
    label: def.label,
    value: pct(run.value.metrics[def.key]),
    baseline: pct(run.value.baseline[def.key]),
  }))
})

const compareRows = computed(() => {
  if (!run.value) return []
  return metricDefs.map((def) => ({
    key: def.key,
    label: def.label,
    current: run.value.metrics[def.key],
    baseline: run.value.baseline[def.key],
  }))
})

const resultRows = computed(() => {
  if (!run.value) return []
  const caseMap = new Map(cases.value.map((item) => [item.id, item]))
  return run.value.results.map((result) => ({
    ...result,
    question: caseMap.get(result.id)?.question ?? '',
  }))
})

async function load() {
  const data = await fetchBenchmark()
  cases.value = data.cases
  run.value = data.last_run
  loading.value = false
}

async function execute() {
  running.value = true
  try {
    run.value = await runBenchmark()
    activeTab.value = 'results'
    ElMessage.success('评测完成（占位数据）')
  } finally {
    running.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <el-card shadow="never">
      <div class="head">
        <div>
          <div class="title">评测集</div>
          <div class="sub">
            上次运行：{{ run?.ran_at ?? '尚未运行' }} · {{ cases.length }} 条用例 ·
            当前为占位数据
          </div>
        </div>
        <el-button type="primary" :loading="running" @click="execute">
          运行评测
        </el-button>
      </div>
    </el-card>

    <el-row :gutter="16" class="row">
      <el-col v-for="card in cards" :key="card.key" :span="6">
        <el-card shadow="never">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-base">单 Agent 基线 {{ card.baseline }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="row">
      <template #header>指标对比</template>
      <el-table :data="compareRows" size="small">
        <el-table-column prop="label" label="指标" min-width="160" />
        <el-table-column label="本系统" width="120">
          <template #default="{ row }">{{ pct(row.current) }}</template>
        </el-table-column>
        <el-table-column label="单 Agent 基线" width="140">
          <template #default="{ row }">{{ pct(row.baseline) }}</template>
        </el-table-column>
        <el-table-column label="差值" width="100">
          <template #default="{ row }">
            {{ delta(row.current, row.baseline) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="row">
      <el-tabs v-model="activeTab">
        <el-tab-pane :label="`用例集 (${cases.length})`" name="cases">
          <el-table :data="cases" size="small">
            <el-table-column prop="id" label="编号" width="90" />
            <el-table-column prop="question" label="问题" min-width="260" />
            <el-table-column prop="expected" label="期望结果" min-width="220" />
            <el-table-column label="标签" min-width="140">
              <template #default="{ row }">
                <el-tag
                  v-for="tag in row.tags"
                  :key="tag"
                  size="small"
                  effect="plain"
                  class="tag"
                >
                  {{ tag }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="本次结果" name="results">
          <el-table :data="resultRows" size="small">
            <el-table-column prop="id" label="编号" width="90" />
            <el-table-column prop="question" label="问题" min-width="260" />
            <el-table-column label="结果" width="90">
              <template #default="{ row }">
                <el-tag
                  size="small"
                  :type="row.passed ? 'success' : 'danger'"
                >
                  {{ row.passed ? '通过' : '未通过' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="note" label="说明" min-width="220" />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.title {
  font-size: 16px;
  font-weight: 600;
}

.sub {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
}

.row {
  margin-top: 16px;
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

.stat-base {
  margin-top: 4px;
  color: #a8abb2;
  font-size: 12px;
}

.tag {
  margin-right: 6px;
}
</style>
