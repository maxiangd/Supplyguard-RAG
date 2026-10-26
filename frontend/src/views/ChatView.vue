<script setup>
import { nextTick, onMounted, reactive, ref } from 'vue'
import { CircleCheck, Clock, Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { fetchChatModels, streamAnswer } from '../api/chat'

const question = ref('')
const running = ref(false)
const messages = ref([])
const citations = ref([])
const graphPaths = ref([])
const steps = ref([])
const riskInfo = ref(null)
const listRef = ref(null)

const models = ref([])
const selectedModel = ref('')
const expandedCitations = ref([])
const openReasoning = ref([])

function toggleReasoning(index) {
  openReasoning.value = openReasoning.value.includes(index)
    ? openReasoning.value.filter((item) => item !== index)
    : [...openReasoning.value, index]
}

function isReasoningOpen(index) {
  return openReasoning.value.includes(index)
}

function citationKey(citation) {
  return `${citation.document_id}-${citation.chunk_index}`
}

function isExpanded(citation) {
  return expandedCitations.value.includes(citationKey(citation))
}

function toggleExpanded(citation) {
  const key = citationKey(citation)
  expandedCitations.value = isExpanded(citation)
    ? expandedCitations.value.filter((item) => item !== key)
    : [...expandedCitations.value, key]
}

const stepDefs = [
  { key: 'intake', label: '接收问题' },
  { key: 'retrieve', label: '权限内检索' },
  { key: 'graph', label: '图谱传导' },
  { key: 'answer', label: '生成结论' },
]

const examples = [
  '碳酸锂价格回落后，Q4 采购策略要怎么调整？',
  '宜春枧下窝锂矿现在复产了吗？',
  '锂电池出口走哪个港口，海运有什么限制？',
  '2025 年营业收入和净利润是多少？',
]

function severityType(severity) {
  if (severity === 'HIGH' || severity === 'CRITICAL') return 'danger'
  return severity === 'MEDIUM' ? 'warning' : 'info'
}

function resetSteps() {
  steps.value = stepDefs.map((step) => ({ ...step, status: 'pending', detail: '' }))
}

function setStep(key, status, detail = '') {
  const step = steps.value.find((item) => item.key === key)
  if (!step) return
  step.status = status
  if (detail) step.detail = detail
}

async function loadModels() {
  try {
    const data = await fetchChatModels()
    models.value = data.models
    const saved = localStorage.getItem('chat_model')
    selectedModel.value = models.value.includes(saved) ? saved : data.default
  } catch {
    models.value = ['deepseek-chat']
    selectedModel.value = 'deepseek-chat'
  }
}

async function ask() {
  const text = question.value.trim()
  if (!text || running.value) return

  messages.value.push({ role: 'user', content: text })
  // 必须是响应式对象，否则逐字追加不会触发视图更新
  const reply = reactive({ role: 'assistant', content: '', reasoning: '' })
  messages.value.push(reply)
  question.value = ''
  citations.value = []
  graphPaths.value = []
  riskInfo.value = null
  expandedCitations.value = []
  resetSteps()
  running.value = true
  setStep('intake', 'done')
  setStep('retrieve', 'active')
  scrollToBottom()

  const model = selectedModel.value
  localStorage.setItem('chat_model', model)
  let streamError = ''

  try {
    await streamAnswer({
      question: text,
      model,
      onEvent: (event) => {
        if (event.type === 'hits') {
          citations.value = event.hits
          setStep('retrieve', 'done', `命中 ${event.hits.length} 段`)
          setStep('graph', 'active')
        } else if (event.type === 'graph') {
          graphPaths.value = event.paths
          setStep(
            'graph',
            'done',
            event.paths.length ? `${event.paths.length} 条路径` : '无命中',
          )
          setStep('answer', 'active')
        } else if (event.type === 'reasoning') {
          reply.reasoning += event.text
          // 思考过程一开始就展开，方便实时看到模型在推理
          const index = messages.value.length - 1
          if (!openReasoning.value.includes(index)) {
            openReasoning.value = [...openReasoning.value, index]
          }
        } else if (event.type === 'risk') {
          riskInfo.value = {
            level: event.level,
            reason: event.reason,
            approval_id: null,
          }
        } else if (event.type === 'approval') {
          if (riskInfo.value) riskInfo.value.approval_id = event.approval_id
        } else if (event.type === 'delta') {
          reply.content += event.text
        } else if (event.type === 'done') {
          citations.value = event.hits
          graphPaths.value = event.graph_paths ?? []
          if (event.approval_id && riskInfo.value) {
            riskInfo.value.approval_id = event.approval_id
          }
          setStep('answer', 'done', model)
        } else if (event.type === 'error') {
          streamError = event.detail
        }
        scrollToBottom()
      },
    })
    if (streamError) throw new Error(streamError)
  } catch (error) {
    const detail = streamError || error.message || '回答失败，请稍后重试'
    reply.content = reply.content || detail
    setStep('answer', 'error', '失败')
    ElMessage.error(detail)
  } finally {
    running.value = false
    scrollToBottom()
  }
}

function useExample(text) {
  question.value = text
  ask()
}

async function scrollToBottom() {
  await nextTick()
  const el = listRef.value
  if (el) el.scrollTop = el.scrollHeight
}

onMounted(loadModels)
</script>

<template>
  <el-row :gutter="16">
    <el-col :span="16">
      <el-card shadow="never" class="chat-card">
        <div ref="listRef" class="messages">
          <div v-if="!messages.length" class="examples">
            <div class="examples-title">可以这样问</div>
            <el-tag
              v-for="item in examples"
              :key="item"
              class="example"
              @click="useExample(item)"
            >
              {{ item }}
            </el-tag>
          </div>

          <div
            v-for="(message, index) in messages"
            :key="index"
            :class="['msg', message.role]"
          >
            <div class="msg-body">
              <div v-if="message.reasoning" class="reasoning">
                <el-button
                  link
                  type="primary"
                  size="small"
                  class="reasoning-toggle"
                  @click="toggleReasoning(index)"
                >
                  {{ isReasoningOpen(index) ? '收起思考过程' : '查看思考过程' }}
                </el-button>
                <div v-if="isReasoningOpen(index)" class="reasoning-text">
                  {{ message.reasoning }}
                </div>
              </div>
              <div
                v-if="message.role === 'user' && message.content"
                class="bubble"
              >
                {{ message.content }}
              </div>
              <div
                v-else-if="
                  message.role === 'assistant' && (message.content || running)
                "
                class="bubble"
              >
                {{ message.content || '正在检索资料…' }}
              </div>
            </div>
          </div>
        </div>

        <div class="composer">
          <el-input
            v-model="question"
            type="textarea"
            :rows="3"
            resize="none"
            placeholder="描述你的风险问题，例如：宜春枧下窝锂矿现在复产了吗？"
            @keydown.enter.exact.prevent="ask"
          />
          <div class="composer-actions">
            <span class="hint">Enter 发送，Shift+Enter 换行 · 回答仅基于当前角色可见资料</span>
            <div class="composer-right">
              <el-select
                v-model="selectedModel"
                size="default"
                style="width: 190px"
                placeholder="选择模型"
              >
                <el-option
                  v-for="model in models"
                  :key="model"
                  :label="model"
                  :value="model"
                />
              </el-select>
              <el-button type="primary" :loading="running" @click="ask">
                提问
              </el-button>
            </div>
          </div>
        </div>
      </el-card>
    </el-col>

    <el-col :span="8">
      <el-card shadow="never" class="side">
        <template #header>执行进度</template>
        <div v-for="step in steps" :key="step.key" class="step">
          <el-icon v-if="step.status === 'done'" color="#67c23a">
            <CircleCheck />
          </el-icon>
          <el-icon
            v-else-if="step.status === 'active'"
            class="is-loading"
            color="#409eff"
          >
            <Loading />
          </el-icon>
          <el-icon v-else color="#c0c4cc"><Clock /></el-icon>
          <span class="step-label">{{ step.label }}</span>
          <span class="step-detail">{{ step.detail }}</span>
        </div>
        <el-empty
          v-if="!steps.length"
          :image-size="50"
          description="提问后显示执行进度"
        />
      </el-card>

      <el-card v-if="riskInfo" shadow="never" class="side risk-side">
        <template #header>
          风险评估
          <el-tag
            :type="riskInfo.level === 'HIGH' ? 'danger' : riskInfo.level === 'MEDIUM' ? 'warning' : 'info'"
            size="small"
            style="margin-left: 8px"
          >
            {{ riskInfo.level }}
          </el-tag>
        </template>
        <div class="risk-reason">{{ riskInfo.reason }}</div>
        <template v-if="riskInfo.level === 'HIGH'">
          <div v-if="riskInfo.approval_id" class="risk-approval">
            审批单号：{{ riskInfo.approval_id }}
          </div>
          <div v-else class="risk-approval risk-pending">
            正在创建审批单…
          </div>
          <router-link to="/review">
            <el-button type="primary" size="small" class="risk-action">
              前往复核台处理
            </el-button>
          </router-link>
        </template>
        <div v-else class="risk-approval">
          {{ riskInfo.level === 'MEDIUM' ? '已标记，可关注后续变化' : '低风险，无需处理' }}
        </div>
      </el-card>

      <el-card shadow="never" class="side">
        <template #header>
          引用与证据
          <span v-if="citations.length" class="filtered">
            （{{ citations.length }} 段）
          </span>
        </template>
        <div
          v-for="(citation, index) in citations"
          :key="citationKey(citation)"
          class="citation"
        >
          <div class="citation-title">
            [{{ index + 1 }}] {{ citation.filename }}
            <span class="chunk">第 {{ citation.chunk_index + 1 }} 块</span>
          </div>
          <div
            :class="['citation-snippet', { expanded: isExpanded(citation) }]"
            @click="toggleExpanded(citation)"
          >
            {{ citation.text }}
          </div>
          <el-button
            v-if="citation.text.length > 120"
            link
            size="small"
            type="primary"
            class="citation-toggle"
            @click="toggleExpanded(citation)"
          >
            {{ isExpanded(citation) ? '收起' : '展开全文' }}
          </el-button>
          <div class="citation-meta">
            <el-tag
              v-for="role in citation.allowed_roles"
              :key="role"
              size="small"
              effect="plain"
            >
              {{ role }}
            </el-tag>
            <span class="citation-score">
              相关度 {{ citation.score.toFixed(3) }}
            </span>
          </div>
        </div>
        <el-empty
          v-if="!citations.length"
          :image-size="50"
          description="回答后显示引用的资料"
        />
      </el-card>

      <el-card shadow="never" class="side">
        <template #header>
          图谱影响路径
          <span v-if="graphPaths.length" class="filtered">
            （{{ graphPaths.length }} 条）
          </span>
        </template>
        <div v-for="(path, index) in graphPaths" :key="index" class="graph-path">
          <div class="graph-path-summary">{{ path.summary }}</div>
          <div class="citation-meta">
            <el-tag size="small" effect="plain">{{ path.rule_label }}</el-tag>
            <el-tag
              size="small"
              effect="plain"
              :type="severityType(path.severity)"
            >
              {{ path.severity }}
            </el-tag>
            <span class="citation-score">{{ path.hops }} 跳</span>
          </div>
          <div class="graph-path-reason">{{ path.reason }}</div>
        </div>
        <el-empty
          v-if="!graphPaths.length"
          :image-size="50"
          description="提问后显示图谱传导路径"
        />
      </el-card>
    </el-col>
  </el-row>
</template>

<style scoped>
.chat-card {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
}

.chat-card :deep(.el-card__body) {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 4px;
}

.examples {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: flex-start;
  padding: 24px 8px;
}

.examples-title {
  color: #909399;
  font-size: 13px;
}

.example {
  cursor: pointer;
}

.msg {
  display: flex;
  margin-bottom: 14px;
}

.msg.user {
  justify-content: flex-end;
}

.msg-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-start;
  max-width: 82%;
}

.msg.user .msg-body {
  align-items: flex-end;
}

.bubble {
  max-width: 100%;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.msg.user .bubble {
  color: #fff;
  background: #1677ff;
}

.msg.assistant .bubble {
  color: #303133;
  background: #f4f6f8;
}

.reasoning {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fafbfc;
}

.reasoning-toggle {
  padding: 0;
  height: auto;
  font-size: 12px;
}

.reasoning-text {
  margin-top: 6px;
  color: #909399;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.risk-side {
  border-left: 3px solid #e6a23c;
}

.risk-reason {
  color: #303133;
  font-size: 13px;
  line-height: 1.6;
}

.risk-approval {
  margin-top: 6px;
  color: #909399;
  font-size: 12px;
}

.risk-pending {
  color: #e6a23c;
}

.risk-action {
  margin-top: 12px;
  width: 100%;
}

.composer {
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.composer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.composer-right {
  display: flex;
  gap: 8px;
  align-items: center;
}

.hint {
  color: #a8abb2;
  font-size: 12px;
}

.side {
  margin-bottom: 16px;
}

.step {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 6px 0;
  font-size: 13px;
}

.step-label {
  width: 96px;
  color: #303133;
}

.step-detail {
  color: #909399;
  font-size: 12px;
}

.filtered {
  color: #909399;
  font-size: 12px;
  font-weight: 400;
}

.citation {
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}

.citation:last-child {
  border-bottom: none;
}

.citation-title {
  font-size: 13px;
  font-weight: 600;
}

.chunk {
  color: #909399;
  font-size: 12px;
  font-weight: 400;
}

.citation-snippet {
  display: -webkit-box;
  overflow: hidden;
  margin: 4px 0;
  color: #606266;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  cursor: pointer;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.citation-snippet.expanded {
  display: block;
  -webkit-line-clamp: unset;
}

.citation-toggle {
  padding: 0;
  height: auto;
  font-size: 12px;
}

.citation-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-top: 6px;
  color: #909399;
  font-size: 12px;
}

.citation-score {
  margin-left: auto;
  white-space: nowrap;
}

.graph-path {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.graph-path:last-child {
  border-bottom: none;
}

.graph-path-summary {
  color: #303133;
  font-size: 12px;
  line-height: 1.6;
}

.graph-path-reason {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
  line-height: 1.6;
}
</style>
