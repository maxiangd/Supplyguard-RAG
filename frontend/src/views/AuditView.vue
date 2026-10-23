<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchAuditLogs } from '../api/mock'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)

const filters = reactive({
  range: [],
  action: '',
  result: '',
  keyword: '',
})

const roleLabels = {
  admin: '管理员',
  procurement: '采购',
  logistics: '物流',
  quality: '质量',
  finance: '财务',
}
const actionLabels = {
  query: '问答查询',
  retrieve: '检索',
  approve: '通过审批',
  reject: '驳回审批',
  upload: '上传文档',
  login: '登录',
  export: '导出',
}
const resultLabels = { allowed: '允许', blocked: '拦截', failed: '失败' }
const resultTypes = { allowed: 'success', blocked: 'danger', failed: 'info' }

async function load() {
  loading.value = true
  try {
    const data = await fetchAuditLogs({
      page: page.value,
      page_size: pageSize.value,
      action: filters.action,
      result: filters.result,
      keyword: filters.keyword.trim(),
      range: filters.range ?? [],
    })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  filters.range = []
  filters.action = ''
  filters.result = ''
  filters.keyword = ''
  page.value = 1
  load()
}

function csvCell(value) {
  let text = String(value ?? '')
  // 防止 Excel 把单元格当公式执行
  if (/^[=+\-@]/.test(text)) {
    text = `'${text}`
  }
  if (/[",\r\n]/.test(text)) {
    text = `"${text.replace(/"/g, '""')}"`
  }
  return text
}

async function exportCsv() {
  const data = await fetchAuditLogs({
    page: 1,
    page_size: total.value || 1000,
    action: filters.action,
    result: filters.result,
    keyword: filters.keyword.trim(),
    range: filters.range ?? [],
  })
  const header = ['时间', '用户', '角色', '租户', '动作', '资源', '结果', 'request_id']
  const lines = [header.join(',')]
  for (const log of data.items) {
    lines.push(
      [
        log.time,
        log.user,
        roleLabels[log.role] ?? log.role,
        log.tenant,
        actionLabels[log.action] ?? log.action,
        log.resource,
        resultLabels[log.result] ?? log.result,
        log.request_id,
      ]
        .map(csvCell)
        .join(','),
    )
  }
  const blob = new Blob([`﻿${lines.join('\r\n')}`], {
    type: 'text/csv;charset=utf-8',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `audit_${Date.now()}.csv`
  link.click()
  URL.revokeObjectURL(url)
  ElMessage.success(`已导出 ${data.items.length} 条记录`)
}

onMounted(load)
</script>

<template>
  <el-card shadow="never">
    <el-form :inline="true" class="filters" @submit.prevent="search">
      <el-form-item label="时间">
        <el-date-picker
          v-model="filters.range"
          type="daterange"
          value-format="YYYY-MM-DD"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="width: 240px"
        />
      </el-form-item>
      <el-form-item label="动作">
        <el-select
          v-model="filters.action"
          clearable
          placeholder="全部"
          style="width: 130px"
        >
          <el-option
            v-for="(label, value) in actionLabels"
            :key="value"
            :label="label"
            :value="value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="结果">
        <el-select
          v-model="filters.result"
          clearable
          placeholder="全部"
          style="width: 110px"
        >
          <el-option
            v-for="(label, value) in resultLabels"
            :key="value"
            :label="label"
            :value="value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input
          v-model="filters.keyword"
          clearable
          placeholder="用户或资源"
          style="width: 160px"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <el-button @click="exportCsv">导出 CSV</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="rows" size="small">
      <el-table-column prop="time" label="时间" width="160" />
      <el-table-column prop="user" label="用户" width="110" />
      <el-table-column label="角色" width="90">
        <template #default="{ row }">
          {{ roleLabels[row.role] ?? '未知' }}
        </template>
      </el-table-column>
      <el-table-column prop="tenant" label="租户" width="90" />
      <el-table-column label="动作" width="100">
        <template #default="{ row }">
          {{ actionLabels[row.action] ?? row.action }}
        </template>
      </el-table-column>
      <el-table-column prop="resource" label="资源" min-width="220" />
      <el-table-column label="结果" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="resultTypes[row.result]">
            {{ resultLabels[row.result] ?? row.result }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="request_id" label="request_id" width="140" />
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="load"
      />
    </div>
  </el-card>
</template>

<style scoped>
.filters {
  margin-bottom: 4px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
