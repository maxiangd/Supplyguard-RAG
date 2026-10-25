<script setup>
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteDocument,
  fetchDocumentChunks,
  fetchDocuments,
  retryDocument,
  updateDocumentRoles,
  uploadDocument,
} from '../api/documents'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const loading = ref(true)
const documents = ref([])

const dialog = ref(false)
const uploading = ref(false)
const selectedFiles = ref([])
const uploadRef = ref(null)
const uploadForm = reactive({ allowedRoles: ['admin'] })

const roleDialog = ref(false)
const roleSaving = ref(false)
const roleEditing = ref(null)
const roleForm = reactive({ allowedRoles: [] })

const chunkDialog = ref(false)
const chunkLoading = ref(false)
const chunkDocument = ref(null)
const chunkList = ref([])

const roleLabels = {
  admin: '管理员',
  procurement: '采购',
  logistics: '物流',
  quality: '质量',
  finance: '财务',
}
const statusLabels = {
  queued: '排队中',
  processing: '处理中',
  ready: '就绪',
  failed: '失败',
}
const statusTypes = {
  queued: 'info',
  processing: 'warning',
  ready: 'success',
  failed: 'danger',
}

let pollTimer = null

async function load() {
  documents.value = await fetchDocuments()
  loading.value = false
}

function formatTime(value) {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function openUploadDialog() {
  selectedFiles.value = []
  uploadForm.allowedRoles = ['admin']
  uploadRef.value?.clearFiles()
  dialog.value = true
}

function handleFileChange(file, fileList) {
  selectedFiles.value = fileList.map((item) => item.raw)
  return false
}

function handleFileRemove(file, fileList) {
  selectedFiles.value = fileList.map((item) => item.raw)
}

async function submitUpload() {
  if (!selectedFiles.value.length) {
    ElMessage.warning('请选择文件')
    return
  }
  if (!uploadForm.allowedRoles.length) {
    ElMessage.warning('请至少选择一个可访问角色')
    return
  }
  uploading.value = true
  let succeeded = 0
  const failed = []
  try {
    for (const file of selectedFiles.value) {
      try {
        await uploadDocument({
          file,
          allowedRoles: uploadForm.allowedRoles,
        })
        succeeded += 1
      } catch (error) {
        failed.push(`${file.name}（${error.response?.data?.detail ?? '上传失败'}）`)
      }
    }
    dialog.value = false
    selectedFiles.value = []
    uploadForm.allowedRoles = ['admin']
    uploadRef.value?.clearFiles()
    await load()
    if (failed.length) {
      ElMessage.warning(
        `成功 ${succeeded} 个，失败 ${failed.length} 个：${failed.join('；')}`,
      )
    } else {
      ElMessage.success(`已上传 ${succeeded} 个文件，正在排队摄取`)
    }
  } finally {
    uploading.value = false
  }
}

async function retry(document) {
  try {
    await retryDocument(document.document_id)
    await load()
    ElMessage.success('已重新投递')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail ?? '操作失败')
  }
}

function canModify(document) {
  return auth.role === 'admin' || document.uploaded_by === auth.user?.username
}

async function remove(document) {
  try {
    await ElMessageBox.confirm(
      `删除「${document.filename}」后，其 ${document.chunk_count} 个向量块也会一并清除，且无法恢复。`,
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  try {
    await deleteDocument(document.document_id)
    await load()
    ElMessage.success('已删除')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail ?? '删除失败')
  }
}

function openRoleDialog(document) {
  roleEditing.value = document
  roleForm.allowedRoles = [...document.allowed_roles]
  roleDialog.value = true
}

async function submitRoles() {
  if (!roleForm.allowedRoles.length) {
    ElMessage.warning('请至少保留一个可访问角色')
    return
  }
  roleSaving.value = true
  try {
    await updateDocumentRoles(roleEditing.value.document_id, roleForm.allowedRoles)
    roleDialog.value = false
    await load()
    ElMessage.success('权限已更新')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail ?? '保存失败')
  } finally {
    roleSaving.value = false
  }
}

async function openChunks(document) {
  chunkDocument.value = document
  chunkList.value = []
  chunkDialog.value = true
  chunkLoading.value = true
  try {
    chunkList.value = await fetchDocumentChunks(document.document_id)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail ?? '加载失败')
  } finally {
    chunkLoading.value = false
  }
}

onMounted(() => {
  load()
  // 有文档在排队/处理中时自动刷新状态
  pollTimer = setInterval(() => {
    if (documents.value.some((doc) => ['queued', 'processing'].includes(doc.status))) {
      load()
    }
  }, 3000)
})

onUnmounted(() => clearInterval(pollTimer))
</script>

<template>
  <el-card v-loading="loading" shadow="never">
    <div class="toolbar">
      <span class="hint">只显示当前角色有权查看的文档</span>
      <el-button type="primary" @click="openUploadDialog">上传文档</el-button>
    </div>

    <el-table :data="documents" size="small">
      <el-table-column prop="filename" label="文件名" min-width="220" />
      <el-table-column label="可访问角色" min-width="220">
        <template #default="{ row }">
          <el-tag
            v-for="role in row.allowed_roles"
            :key="role"
            size="small"
            effect="plain"
            class="tag"
          >
            {{ roleLabels[role] ?? role }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="statusTypes[row.status]">
            {{ statusLabels[row.status] ?? row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="chunk_count" label="块数" width="80" />
      <el-table-column prop="uploaded_by" label="上传人" width="150" />
      <el-table-column label="上传时间" width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="270">
        <template #default="{ row }">
          <el-button link type="primary" @click="openChunks(row)">
            查看
          </el-button>
          <el-button
            v-if="row.status === 'failed' && canModify(row)"
            link
            type="primary"
            @click="retry(row)"
          >
            重新摄取
          </el-button>
          <el-button
            v-if="auth.role === 'admin'"
            link
            type="primary"
            @click="openRoleDialog(row)"
          >
            权限
          </el-button>
          <el-button
            v-if="canModify(row)"
            link
            type="danger"
            @click="remove(row)"
          >
            删除
          </el-button>
          <span v-if="!canModify(row) && auth.role !== 'admin'" class="muted">
            —
          </span>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && !documents.length" description="还没有文档" />
  </el-card>

  <el-dialog v-model="dialog" title="上传文档" width="460px">
    <el-form label-width="90px">
      <el-form-item label="文件">
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          multiple
          accept=".pdf,.txt,.md"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
        >
          <el-button>选择文件</el-button>
          <template #tip>
            <div class="muted">可多选，支持 PDF / TXT / Markdown，单个最大 20 MB</div>
          </template>
        </el-upload>
      </el-form-item>
      <el-form-item label="可访问角色">
        <el-select
          v-model="uploadForm.allowedRoles"
          multiple
          style="width: 100%"
          placeholder="选择可检索该文档的角色"
        >
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
      <el-button @click="dialog = false">取消</el-button>
      <el-button type="primary" :loading="uploading" @click="submitUpload">
        上传
      </el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="roleDialog" title="调整可访问角色" width="420px">
    <p class="muted">{{ roleEditing?.filename }}</p>
    <el-select
      v-model="roleForm.allowedRoles"
      multiple
      style="width: 100%"
      placeholder="选择可检索该文档的角色"
    >
      <el-option
        v-for="(label, value) in roleLabels"
        :key="value"
        :label="label"
        :value="value"
      />
    </el-select>
    <template #footer>
      <el-button @click="roleDialog = false">取消</el-button>
      <el-button type="primary" :loading="roleSaving" @click="submitRoles">
        保存
      </el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="chunkDialog"
    :title="`切块内容 · ${chunkDocument?.filename ?? ''}`"
    width="720px"
  >
    <div v-loading="chunkLoading" class="chunks">
      <div v-for="chunk in chunkList" :key="chunk.chunk_index" class="chunk">
        <div class="chunk-index">第 {{ chunk.chunk_index + 1 }} 块</div>
        <div class="chunk-text">{{ chunk.text }}</div>
      </div>
      <el-empty
        v-if="!chunkLoading && !chunkList.length"
        :image-size="60"
        description="还没有切块内容"
      />
    </div>
    <template #footer>
      <el-button @click="chunkDialog = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.hint,
.muted {
  color: #909399;
  font-size: 13px;
}

.tag {
  margin-right: 6px;
}

.chunks {
  max-height: 60vh;
  overflow-y: auto;
}

.chunk {
  margin-bottom: 14px;
}

.chunk-index {
  margin-bottom: 4px;
  color: #909399;
  font-size: 12px;
}

.chunk-text {
  padding: 8px 10px;
  border-radius: 6px;
  background: #f7f8fa;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}
</style>
