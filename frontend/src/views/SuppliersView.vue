<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { ElMessage } from 'element-plus'
import { analyzeImpact, fetchGraphOverview } from '../api/graph'

use([CanvasRenderer, GraphChart, LegendComponent, TooltipComponent])

const loading = ref(true)
const graph = ref({ nodes: [], links: [] })
const selectedId = ref('')
const highOnly = ref(false)
const impactPaths = ref([])
const impactLoading = ref(false)

const typeLabels = {
  supplier: '供应商',
  factory: '工厂',
  port: '港口',
  route: '航线',
  region: '地区',
  event: '风险事件',
}
const typeColors = {
  supplier: '#1677ff',
  factory: '#67c23a',
  port: '#e6a23c',
  route: '#9254de',
  region: '#909399',
  event: '#f56c6c',
}
const typeSize = { supplier: 46, factory: 38, port: 32, route: 30, region: 36, event: 28 }
const levelText = { high: '高', medium: '中', low: '低' }
const levelType = { high: 'danger', medium: 'warning', low: 'success' }
const riskBorder = { high: '#f56c6c', medium: '#e6a23c', low: '#67c23a' }

function severityType(severity) {
  if (severity === 'HIGH' || severity === 'CRITICAL') return 'danger'
  return severity === 'MEDIUM' ? 'warning' : 'info'
}

const nodeMap = computed(
  () => new Map(graph.value.nodes.map((node) => [node.id, node])),
)
const selectedNode = computed(() => nodeMap.value.get(selectedId.value) ?? null)

const visibleNodes = computed(() =>
  graph.value.nodes.filter(
    (node) => !highOnly.value || node.risk_level === 'high',
  ),
)
const visibleLinks = computed(() => {
  const ids = new Set(visibleNodes.value.map((node) => node.id))
  return graph.value.links.filter(
    (link) => ids.has(link.source) && ids.has(link.target),
  )
})

const neighborIds = computed(() => {
  const ids = new Set()
  if (!selectedId.value) return ids
  ids.add(selectedId.value)
  for (const link of visibleLinks.value) {
    if (link.source === selectedId.value) ids.add(link.target)
    if (link.target === selectedId.value) ids.add(link.source)
  }
  return ids
})

const option = computed(() => {
  const hasSelection = Boolean(selectedId.value)
  return {
    tooltip: {
      formatter: (params) => {
        if (params.dataType === 'edge') {
          const from =
            nodeMap.value.get(params.data.source)?.name ?? params.data.source
          const to =
            nodeMap.value.get(params.data.target)?.name ?? params.data.target
          return `${from} → ${to}<br/>${params.data.relation}${
            params.data.detail ? `<br/>${params.data.detail}` : ''
          }`
        }
        return `${params.name}<br/>${typeLabels[params.data.type]}`
      },
    },
    legend: { top: 4, data: Object.values(typeLabels) },
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        categories: Object.entries(typeLabels).map(([key, name]) => ({
          name,
          itemStyle: { color: typeColors[key] },
        })),
        data: visibleNodes.value.map((node) => {
          const dimmed = hasSelection && !neighborIds.value.has(node.id)
          return {
            id: node.id,
            name: node.name,
            type: node.type,
            category: Object.keys(typeLabels).indexOf(node.type),
            symbolSize: typeSize[node.type],
            itemStyle: {
              opacity: dimmed ? 0.2 : 1,
              color: typeColors[node.type],
              borderColor: riskBorder[node.risk_level] ?? '#dcdfe6',
              borderWidth: node.risk_level === 'high' ? 4 : 1,
            },
            label: {
              show: true,
              fontSize: 11,
              color: dimmed ? '#c0c4cc' : '#303133',
            },
          }
        }),
        links: visibleLinks.value.map((link) => {
          const related =
            link.source === selectedId.value ||
            link.target === selectedId.value
          return {
            source: link.source,
            target: link.target,
            relation: link.relation,
            detail: link.detail,
            lineStyle: {
              color: hasSelection && !related ? '#eeeeee' : '#c0c4cc',
              width: related ? 2.5 : 1.5,
            },
          }
        }),
        force: { repulsion: 320, edgeLength: [90, 150] },
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: 6,
        lineStyle: { curveness: 0.08 },
        emphasis: { focus: 'adjacency' },
      },
    ],
  }
})

const relatedLinks = computed(() => {
  if (!selectedNode.value) return []
  const id = selectedNode.value.id
  return visibleLinks.value
    .filter((link) => link.source === id || link.target === id)
    .map((link) => {
      const outgoing = link.source === id
      const otherId = outgoing ? link.target : link.source
      const other = nodeMap.value.get(otherId)
      return {
        key: `${link.source}-${link.target}-${link.relation}`,
        otherId,
        otherName: other?.name ?? otherId,
        otherType: other?.type ?? '',
        relation: link.relation,
        detail: link.detail,
        outgoing,
      }
    })
})

const relatedEvents = computed(() =>
  relatedLinks.value.filter((item) => item.otherType === 'event'),
)

function onChartClick(params) {
  if (params.dataType === 'node') {
    selectedId.value = params.data.id
  }
}

watch(selectedId, async (id) => {
  impactPaths.value = []
  if (!id) return
  impactLoading.value = true
  try {
    const data = await analyzeImpact({ entityId: id, maxHops: 3 })
    impactPaths.value = data.paths.slice(0, 8)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail ?? '影响分析失败')
  } finally {
    impactLoading.value = false
  }
})

onMounted(async () => {
  try {
    graph.value = await fetchGraphOverview()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail ?? '图谱加载失败')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <el-row v-loading="loading" :gutter="16">
    <el-col :span="17">
      <el-card shadow="never" class="graph-card">
        <template #header>
          <div class="toolbar">
            <el-select
              v-model="selectedId"
              filterable
              clearable
              placeholder="搜索节点"
              class="search"
            >
              <el-option
                v-for="node in graph.nodes"
                :key="node.id"
                :label="`${node.name}（${typeLabels[node.type]}）`"
                :value="node.id"
              />
            </el-select>
            <el-switch v-model="highOnly" active-text="只看高风险" />
            <el-button link type="primary" @click="selectedId = ''">
              重置
            </el-button>
          </div>
        </template>
        <v-chart
          class="chart"
          :option="option"
          autoresize
          @click="onChartClick"
        />
      </el-card>
    </el-col>

    <el-col :span="7">
      <el-card shadow="never" class="detail-card">
        <template v-if="selectedNode">
          <div class="detail-name">{{ selectedNode.name }}</div>
          <div class="detail-tags">
            <el-tag size="small">{{ typeLabels[selectedNode.type] }}</el-tag>
            <el-tag size="small" :type="levelType[selectedNode.risk_level]">
              风险{{ levelText[selectedNode.risk_level] }}
            </el-tag>
            <el-tag size="small" type="info" effect="plain">
              {{ selectedNode.region }}
            </el-tag>
          </div>
          <p class="desc">{{ selectedNode.desc }}</p>

          <div class="section-title">关联关系</div>
          <div v-for="rel in relatedLinks" :key="rel.key" class="rel-row">
            <span class="rel-other">
              {{ rel.outgoing ? '→' : '←' }} {{ rel.otherName }}
            </span>
            <el-tag size="small" effect="plain" :title="rel.detail">
              {{ rel.relation }}
            </el-tag>
          </div>

          <div class="section-title">相关风险事件</div>
          <div v-if="relatedEvents.length" class="events">
            <el-alert
              v-for="event in relatedEvents"
              :key="event.key"
              :title="event.otherName"
              type="warning"
              :closable="false"
            />
          </div>
          <div v-else class="empty-text">暂无关联事件</div>

          <div class="section-title">多跳影响路径</div>
          <div v-loading="impactLoading" class="events">
            <div v-for="path in impactPaths" :key="path.summary" class="path-row">
              <div class="path-summary">{{ path.summary }}</div>
              <div class="path-meta">
                <el-tag size="small" effect="plain">{{ path.rule_label }}</el-tag>
                <el-tag
                  size="small"
                  effect="plain"
                  :type="severityType(path.severity)"
                >
                  {{ path.hops }} 跳
                </el-tag>
              </div>
            </div>
            <div
              v-if="!impactLoading && !impactPaths.length"
              class="empty-text"
            >
              暂无下游影响路径
            </div>
          </div>
        </template>
        <el-empty v-else description="点击图中节点查看详情" />
      </el-card>
    </el-col>
  </el-row>
</template>

<style scoped>
.toolbar {
  display: flex;
  gap: 16px;
  align-items: center;
}

.search {
  width: 240px;
}

.chart {
  height: calc(100vh - 220px);
  min-height: 480px;
}

.detail-card {
  height: calc(100vh - 160px);
  overflow-y: auto;
}

.detail-name {
  font-size: 18px;
  font-weight: 600;
}

.detail-tags {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.desc {
  margin: 12px 0;
  color: #606266;
  font-size: 13px;
  line-height: 1.7;
}

.section-title {
  margin: 16px 0 8px;
  color: #909399;
  font-size: 12px;
}

.rel-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid #f5f5f5;
  font-size: 13px;
}

.rel-other {
  color: #303133;
}

.events {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.path-row {
  padding: 8px 10px;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
}

.path-summary {
  color: #303133;
  font-size: 12px;
  line-height: 1.6;
}

.path-meta {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}

.empty-text {
  color: #a8abb2;
  font-size: 13px;
}
</style>
