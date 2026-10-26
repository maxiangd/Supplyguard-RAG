<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { clearAuditLogs, fetchAuditLogs } from '../api/audit'

const loading = ref(false)
const rows = ref([])
const total = ref(0)

const roleLabels = {
  admin: '管理员',
  procurement: '采购',
  logistics: '物流',
  quality: '质量',
  finance: '财务',
}
const actionLabels = {
  'approval.created': '提交审批',
  'approval.approve': '通过审批',
  'approval.reject': '驳回审批',
}

function formatTime(value) {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

async function load() {
  loading.value = true
  try {
    rows.value = await fetchAuditLogs(100)
    total.value = rows.value.length
  } catch (error) {
    ElMessage.error(error.response?.data?.detail ?? '加载失败')
  } finally {
    loading.value = false
  }
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

function exportCsv() {
  const header = ['时间', '用户', '角色', '动作', '对象', '详情']
  const lines = [header.join(',')]
  for (const log of rows.value) {
    lines.push(
      [
        formatTime(log.created_at),
        log.actor,
        roleLabels[log.actor_role] ?? log.actor_role,
        actionLabels[log.action] ?? log.action,
        log.target_id ?? '',
        JSON.stringify(log.detail ?? {}),
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
  ElMessage.success(`已导出 ${total.value} 条记录`)
}

async function clearAll() {
  try {
    await ElMessageBox.confirm(
      '确定要清空全部审计日志吗？此操作不可恢复。',
      '确认清空',
      { confirmButtonText: '清空', cancelButtonText: '取消', type: 'danger' },
    )
  } catch {
    return
  }
  try {
    const result = await clearAuditLogs()
    ElMessage.success(`已清空 ${result.deleted} 条日志`)
    await load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail ?? '清空失败')
  }
}

onMounted(load)
</script>

<template>
  <el-card shadow="never">
    <div class="toolbar">
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
      <el-button @click="exportCsv">导出 CSV</el-button>
      <el-button type="danger" plain @click="clearAll">清空日志</el-button>
      <span class="hint">仅记录审批全链路</span>
    </div>

    <el-table v-loading="loading" :data="rows" size="small">
      <el-table-column label="时间" width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column prop="actor" label="用户" width="120" />
      <el-table-column label="角色" width="90">
        <template #default="{ row }">
          {{ roleLabels[row.actor_role] ?? '未知' }}
        </template>
      </el-table-column>
      <el-table-column label="动作" width="110">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">
            {{ actionLabels[row.action] ?? row.action }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="target_id" label="对象" width="210" />
      <el-table-column label="详情" min-width="240">
        <template #default="{ row }">
          {{ row.detail ? JSON.stringify(row.detail) : '—' }}
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.hint {
  color: #a8abb2;
  font-size: 12px;
}
</style>