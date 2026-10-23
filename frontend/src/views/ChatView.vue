<script setup>
import { nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'
import { CircleCheck, Clock, Loading } from '@element-plus/icons-vue'
import { runWorkflow } from '../api/mock'

const router = useRouter()

const question = ref('')
const running = ref(false)
const messages = ref([])
const citations = ref([])
const graphPaths = ref([])
const approval = ref(null)
const filteredCount = ref(0)
const steps = ref([])
const listRef = ref(null)

const stepDefs = [
  { key: 'intake', label: '接收问题' },
  { key: 'classify', label: '意图分类' },
  { key: 'retrieve', label: '权限内检索' },
  { key: 'graph', label: '图谱影响分析' },
  { key: 'review', label: '权限复核' },
  { key: 'synthesize', label: '生成结论' },
]

const examples = [
  '赣锋锂业供应波动会影响 Q4 电芯交付吗？',
  '红海绕行应该启用中欧班列吗？',
  '刚果（金）钴出口配额影响哪些基地？',
]

function resetRun() {
  steps.value = stepDefs.map((step) => ({
    ...step,
    status: 'pending',
    detail: '',
  }))
  citations.value = []
  graphPaths.value = []
  approval.value = null
  filteredCount.value = 0
}

function setStep(key, status, detail = '') {
  const step = steps.value.find((item) => item.key === key)
  if (!step) return
  step.status = status
  if (detail) step.detail = detail
}

function handleEvent(event) {
  const current = messages.value[messages.value.length - 1]
  switch (event.type) {
    case 'run_started':
      setStep('intake', 'done')
      setStep('classify', 'active')
      break
    case 'classify_done':
      setStep('classify', 'done', event.label)
      setStep('retrieve', 'active')
      break
    case 'retrieve_done':
      setStep(
        'retrieve',
        'done',
        `命中 ${event.hits} 段，过滤 ${event.filtered} 段`,
      )
      setStep('graph', 'active')
      break
    case 'graph_done':
      setStep('graph', 'done', `${event.paths} 条传导路径`)
      setStep('review', 'active')
      break
    case 'review_done':
      setStep('review', 'done', event.note)
      setStep('synthesize', 'active')
      break
    case 'token':
      current.content += event.text
      scrollToBottom()
      break
    case 'done':
      setStep('synthesize', 'done')
      current.content = event.result.answer
      citations.value = event.result.citations
      graphPaths.value = event.result.graph_paths
      approval.value = event.result.approval_required
        ? event.result.approval_reason
        : null
      filteredCount.value = event.result.filtered_count
      break
  }
}

async function ask() {
  const text = question.value.trim()
  if (!text || running.value) return

  messages.value.push({ role: 'user', content: text })
  messages.value.push({ role: 'assistant', content: '' })
  question.value = ''
  resetRun()
  running.value = true
  scrollToBottom()

  try {
    await runWorkflow({ question: text }, handleEvent)
  } finally {
    running.value = false
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
            <div class="bubble">
              {{ message.content || (message.role === 'assistant' && running ? '正在分析…' : '') }}
            </div>
          </div>
        </div>

        <div class="composer">
          <el-input
            v-model="question"
            type="textarea"
            :rows="3"
            resize="none"
            placeholder="描述你的风险问题，例如：赣锋锂业供应波动会影响 Q4 电芯交付吗？"
            @keydown.enter.exact.prevent="ask"
          />
          <div class="composer-actions">
            <span class="hint">
              Enter 发送，Shift+Enter 换行 · 当前为占位数据
            </span>
            <el-button type="primary" :loading="running" @click="ask">
              提问
            </el-button>
          </div>
        </div>
      </el-card>
    </el-col>

    <el-col :span="8">
      <el-card shadow="never" class="side">
        <template #header>工作流进度</template>
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

      <el-alert
        v-if="approval"
        type="warning"
        :closable="false"
        class="approval"
        show-icon
      >
        <template #title>该结论需人工复核</template>
        <div class="approval-text">{{ approval }}</div>
        <el-button type="warning" link @click="router.push('/review')">
          去复核台处理 →
        </el-button>
      </el-alert>

      <el-card shadow="never" class="side">
        <template #header>
          引用与证据
          <span v-if="filteredCount" class="filtered">
            （另有 {{ filteredCount }} 条因权限被过滤）
          </span>
        </template>
        <div v-for="citation in citations" :key="citation.id" class="citation">
          <div class="citation-title">[{{ citation.id }}] {{ citation.title }}</div>
          <div class="citation-snippet">{{ citation.snippet }}</div>
          <div class="citation-meta">
            <el-tag
              v-for="role in citation.allowed_roles"
              :key="role"
              size="small"
              effect="plain"
            >
              {{ role }}
            </el-tag>
            <span v-if="citation.score">相关度 {{ citation.score }}</span>
          </div>
        </div>
        <el-empty
          v-if="!citations.length"
          :image-size="50"
          description="回答后显示可引用的证据"
        />
      </el-card>

      <el-card v-if="graphPaths.length" shadow="never" class="side">
        <template #header>图谱路径</template>
        <div v-for="path in graphPaths" :key="path.id" class="path">
          <div class="path-nodes">{{ path.nodes.join(' → ') }}</div>
          <div class="path-meta">
            <el-tag
              size="small"
              :type="path.risk === 'high' ? 'danger' : 'warning'"
            >
              {{ path.relation }}
            </el-tag>
          </div>
        </div>
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

.bubble {
  max-width: 82%;
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

.approval {
  margin-bottom: 16px;
}

.approval-text {
  margin: 4px 0;
  font-size: 13px;
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

.citation-snippet {
  margin: 4px 0;
  color: #606266;
  font-size: 12px;
  line-height: 1.6;
}

.citation-meta {
  display: flex;
  gap: 6px;
  align-items: center;
  color: #909399;
  font-size: 12px;
}

.path-nodes {
  font-size: 13px;
  line-height: 1.6;
}

.path-meta {
  margin-top: 4px;
}
</style>
