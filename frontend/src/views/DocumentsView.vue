<script setup>
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchDocuments, retryDocument, uploadDocument } from '../api/documents'

const loading = ref(true)
const documents = ref([])

const dialog = ref(false)
const uploading = ref(false)
const selectedFile = ref(null)
const uploadForm = reactive({ allowedRoles: ['admin'] })

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

function handleFileChange(file) {
  selectedFile.value = file.raw
  return false
}

function handleFileRemove() {
  selectedFile.value = null
}

async function submitUpload() {
  if (!selectedFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  if (!uploadForm.allowedRoles.length) {
    ElMessage.warning('请至少选择一个可访问角色')
    return
  }
  uploading.value = true
  try {
    await uploadDocument({
      file: selectedFile.value,
      allowedRoles: uploadForm.allowedRoles,
    })
    dialog.value = false
    selectedFile.value = null
    uploadForm.allowedRoles = ['admin']
    await load()
    ElMessage.success('已上传，正在排队摄取')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail ?? '上传失败')
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
      <el-button type="primary" @click="dialog = true">上传文档</el-button>
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
      <el-table-column label="操作" width="110">
        <template #default="{ row }">
          <el-button
            v-if="row.status === 'failed'"
            link
            type="primary"
            @click="retry(row)"
          >
            重新摄取
          </el-button>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && !documents.length" description="还没有文档" />
  </el-card>

  <el-dialog v-model="dialog" title="上传文档" width="460px">
    <el-form label-width="90px">
      <el-form-item label="文件">
        <el-upload
          :auto-upload="false"
          :limit="1"
          accept=".pdf,.txt,.md"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
        >
          <el-button>选择文件</el-button>
          <template #tip>
            <div class="muted">支持 PDF / TXT / Markdown，最大 20 MB</div>
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
</style>
