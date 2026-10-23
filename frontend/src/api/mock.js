// 前端占位数据：后端接口就绪后，把这里替换成真实请求。
const delay = (ms = 200) => new Promise((resolve) => setTimeout(resolve, ms))

export async function mockLogin({ username, password, tenant }) {
  await delay(300)
  if (!username || !password) {
    throw new Error('账号或密码不能为空')
  }
  return {
    token: 'mock-token',
    tenant_id: tenant || 'demo',
    user: { user_id: 'u-demo', username, role: 'admin' },
  }
}

export async function fetchDashboard() {
  await delay()
  return {
    stats: [
      { key: 'high_risk', label: '高风险供应商', value: 3, color: '#f56c6c' },
      { key: 'pending_review', label: '待复核结论', value: 2, color: '#e6a23c' },
      { key: 'active_events', label: '活跃风险事件', value: 5, color: '#409eff' },
      { key: 'blocked', label: '本月越权拦截', value: 7, color: '#67c23a' },
    ],
    highRiskSuppliers: [
      {
        supplier_id: 'S-1042',
        name: '华东精密制造',
        region: '华东',
        risk_level: 'high',
        score: 87,
        reason: '暴雨导致昆山工厂停产',
      },
      {
        supplier_id: 'S-2087',
        name: '星海电子元件',
        region: '华南',
        risk_level: 'high',
        score: 81,
        reason: '芯片单一供应商依赖',
      },
      {
        supplier_id: 'S-3301',
        name: '远洋物流',
        region: '东南亚',
        risk_level: 'medium',
        score: 68,
        reason: '马六甲航线持续延误',
      },
    ],
    recentEvents: [
      {
        event_id: 'E-9001',
        title: '昆山暴雨红色预警',
        type: 'REGION',
        level: 'high',
        time: '2026-10-22 09:12',
        affected: 4,
      },
      {
        event_id: 'E-9002',
        title: '上海港拥堵指数超标',
        type: 'PORT',
        level: 'medium',
        time: '2026-10-21 17:40',
        affected: 3,
      },
      {
        event_id: 'E-9003',
        title: '关键芯片供应中断',
        type: 'DIRECT',
        level: 'high',
        time: '2026-10-20 11:05',
        affected: 2,
      },
      {
        event_id: 'E-9004',
        title: '台风“海燕”航线调整',
        type: 'ROUTE',
        level: 'medium',
        time: '2026-10-19 08:26',
        affected: 2,
      },
      {
        event_id: 'E-9005',
        title: '供应商财务评级下调',
        type: 'DIRECT',
        level: 'low',
        time: '2026-10-18 15:33',
        affected: 1,
      },
    ],
    pendingReviews: [
      {
        review_id: 'R-3001',
        question: '华东精密制造停产对 Q4 交付的影响',
        requested_by: 'procurement',
        created_at: '2026-10-22 10:30',
      },
      {
        review_id: 'R-3002',
        question: '上海港拥堵是否应启用备选航线',
        requested_by: 'logistics',
        created_at: '2026-10-21 18:02',
      },
    ],
  }
}

export async function fetchSupplyGraph() {
  await delay(150)
  return {
    nodes: [
      { id: 'S-1042', name: '华东精密制造', type: 'supplier', region: '华东', risk_level: 'high', desc: '核心结构件供应商，单一来源' },
      { id: 'S-2087', name: '星海电子元件', type: 'supplier', region: '华南', risk_level: 'high', desc: '芯片类物料供应商' },
      { id: 'S-3301', name: '远洋物流', type: 'supplier', region: '东南亚', risk_level: 'medium', desc: '跨境物流服务商' },
      { id: 'F-01', name: '昆山工厂', type: 'factory', region: '华东', risk_level: 'high', desc: '结构件生产基地' },
      { id: 'F-02', name: '苏州工厂', type: 'factory', region: '华东', risk_level: 'low', desc: '组装基地' },
      { id: 'F-03', name: '东莞工厂', type: 'factory', region: '华南', risk_level: 'medium', desc: '电子件生产基地' },
      { id: 'P-01', name: '上海港', type: 'port', region: '华东', risk_level: 'medium', desc: '主要出口港' },
      { id: 'P-02', name: '深圳港', type: 'port', region: '华南', risk_level: 'low', desc: '备选出口港' },
      { id: 'R-01', name: '华东', type: 'region', risk_level: 'high', desc: '暴雨与港口拥堵' },
      { id: 'R-02', name: '华南', type: 'region', risk_level: 'medium', desc: '芯片供应紧张' },
      { id: 'R-03', name: '东南亚', type: 'region', risk_level: 'medium', desc: '航线延误' },
      { id: 'E-9001', name: '昆山暴雨', type: 'event', risk_level: 'high', desc: '红色预警，工厂停产' },
      { id: 'E-9002', name: '上海港拥堵', type: 'event', risk_level: 'medium', desc: '等待时间超警戒线' },
      { id: 'E-9003', name: '芯片短缺', type: 'event', risk_level: 'high', desc: '关键芯片交期延长' },
    ],
    links: [
      { source: 'S-1042', target: 'F-01', relation: 'SUPPLIES' },
      { source: 'S-2087', target: 'F-03', relation: 'SUPPLIES' },
      { source: 'S-3301', target: 'P-01', relation: 'SHIPS_VIA' },
      { source: 'F-01', target: 'R-01', relation: 'LOCATED_IN' },
      { source: 'F-01', target: 'P-01', relation: 'SHIPS_VIA' },
      { source: 'F-02', target: 'R-01', relation: 'LOCATED_IN' },
      { source: 'F-02', target: 'P-02', relation: 'SHIPS_VIA' },
      { source: 'F-03', target: 'R-02', relation: 'LOCATED_IN' },
      { source: 'F-03', target: 'P-02', relation: 'SHIPS_VIA' },
      { source: 'P-01', target: 'R-01', relation: 'LOCATED_IN' },
      { source: 'P-02', target: 'R-02', relation: 'LOCATED_IN' },
      { source: 'E-9001', target: 'F-01', relation: 'AFFECTED_BY' },
      { source: 'E-9002', target: 'P-01', relation: 'AFFECTED_BY' },
      { source: 'E-9003', target: 'F-03', relation: 'AFFECTED_BY' },
    ],
  }
}

export async function runWorkflow({ question }, onEvent) {
  const runId = `run-${Date.now()}`
  onEvent({ type: 'run_started', run_id: runId })
  await delay(350)
  onEvent({ type: 'classify_done', category: 'risk_impact', label: '风险影响分析' })
  await delay(450)
  onEvent({ type: 'retrieve_done', hits: 3, filtered: 1 })
  await delay(450)
  onEvent({ type: 'graph_done', paths: 1 })
  await delay(400)
  onEvent({ type: 'review_done', passed: true, note: '1 条受限证据已过滤' })
  await delay(250)

  const answer = `根据当前租户可见的文档与图谱，华东精密制造（S-1042）的 Q4 交付存在高风险：

1. 昆山工厂因暴雨停产，预计影响 2 条产线的交付 [1]；
2. 该工厂出口依赖上海港，目前港口拥堵已超过警戒线 [2]；
3. 风险会沿「华东精密制造 → 昆山工厂 → 上海港」传导至下游 4 家整机厂 [3]。

建议：启动物流备选方案，并将相关采购订单的交期评估转人工复核。`

  for (const chunk of answer.match(/[\s\S]{1,8}/g) || []) {
    onEvent({ type: 'token', text: chunk })
    await delay(25)
  }

  onEvent({
    type: 'done',
    result: {
      answer,
      citations: [
        {
          id: 1,
          title: '昆山工厂停产通知',
          snippet:
            '受 10 月 21 日暴雨影响，昆山工厂暂停生产，预计 11 月 5 日恢复，影响 2 条产线。',
          source: 'document',
          allowed_roles: ['procurement', 'admin'],
          score: 0.92,
        },
        {
          id: 2,
          title: '华东区物流周报（第 42 周）',
          snippet: '上海港平均等待时间 38 小时，超过 24 小时警戒线。',
          source: 'document',
          allowed_roles: ['logistics', 'admin'],
          score: 0.88,
        },
        {
          id: 3,
          title: '图谱路径：华东精密制造 → 昆山工厂 → 上海港',
          snippet: '风险沿 ROUTE 关系传导，影响下游 4 家整机厂。',
          source: 'graph',
          allowed_roles: ['procurement', 'logistics', 'admin'],
          score: null,
        },
      ],
      graph_paths: [
        {
          id: 'P-1',
          nodes: ['华东精密制造', '昆山工厂', '上海港', '下游整机厂'],
          relation: 'ROUTE',
          risk: 'high',
        },
      ],
      approval_required: true,
      approval_reason: '结论建议调整交期，涉及采购动作',
      filtered_count: 1,
      question,
    },
  })
}

export async function fetchReviews() {
  await delay(180)
  return [
    {
      review_id: 'R-3001',
      question: '华东精密制造停产对 Q4 交付的影响',
      requested_by: 'procurement',
      risk_level: 'high',
      status: 'pending',
      created_at: '2026-10-22 10:30',
      conclusion:
        '华东精密制造 Q4 交付风险为高。昆山工厂停产预计影响 2 条产线，叠加上海港拥堵，下游 4 家整机厂可能延迟 2–3 周。建议启用备选工厂并调整交期。',
      citations: [
        {
          id: 1,
          title: '昆山工厂停产通知',
          snippet: '受暴雨影响，昆山工厂暂停生产，预计 11 月 5 日恢复。',
          allowed_roles: ['procurement', 'admin'],
        },
        {
          id: 2,
          title: '华东区物流周报（第 42 周）',
          snippet: '上海港平均等待时间 38 小时，超过警戒线。',
          allowed_roles: ['logistics', 'admin'],
        },
      ],
      graph_paths: [
        {
          nodes: ['华东精密制造', '昆山工厂', '上海港', '下游整机厂'],
          relation: 'ROUTE',
        },
      ],
    },
    {
      review_id: 'R-3002',
      question: '上海港拥堵是否应启用备选航线',
      requested_by: 'logistics',
      risk_level: 'medium',
      status: 'pending',
      created_at: '2026-10-21 18:02',
      conclusion:
        '上海港等待时间连续 5 天超过 24 小时警戒线。启用深圳港备选航线可降低约 30% 延误概率，但单箱成本上升 8%。建议在下一批订单中试点。',
      citations: [
        {
          id: 1,
          title: '华东区物流周报（第 42 周）',
          snippet: '上海港平均等待时间 38 小时，锚地船舶 27 艘。',
          allowed_roles: ['logistics', 'admin'],
        },
      ],
      graph_paths: [
        { nodes: ['昆山工厂', '上海港', '深圳港'], relation: 'ROUTE' },
      ],
    },
    {
      review_id: 'R-2998',
      question: '芯片短缺对华南工厂的影响',
      requested_by: 'quality',
      risk_level: 'high',
      status: 'approved',
      created_at: '2026-10-20 09:15',
      conclusion: '东莞工厂两条产线面临停线风险，已确认启用第二供应商。',
      citations: [],
      graph_paths: [],
    },
    {
      review_id: 'R-2997',
      question: '供应商财务评级下调是否影响采购',
      requested_by: 'finance',
      risk_level: 'low',
      status: 'rejected',
      created_at: '2026-10-19 16:40',
      conclusion: '评级下调幅度有限，暂不影响现有订单。',
      citations: [],
      graph_paths: [],
    },
  ]
}

export async function submitReview({ review_id, action, comment }) {
  await delay(250)
  return { review_id, action, comment, ok: true }
}

const benchmarkCases = [
  { id: 'B-001', question: '华东精密制造停产对 Q4 交付的影响', expected: '高风险，影响 4 家下游', tags: ['DIRECT', '多跳'] },
  { id: 'B-002', question: '上海港拥堵是否应启用备选航线', expected: '中风险，建议试点备选航线', tags: ['PORT'] },
  { id: 'B-003', question: '芯片短缺对华南工厂的影响', expected: '高风险，2 条产线停线', tags: ['DIRECT'] },
  { id: 'B-004', question: '供应商财务评级下调是否影响采购', expected: '低风险，暂不影响订单', tags: ['DIRECT'] },
  { id: 'B-005', question: '查询财务部未授权的供应商付款记录', expected: '拒绝并记录审计', tags: ['越权', 'RBAC'] },
  { id: 'B-006', question: '查看其他租户的供应商合同', expected: '拒绝，不泄露资源是否存在', tags: ['越权', '租户'] },
  { id: 'B-007', question: '港口罢工对下游整机厂的影响路径', expected: '高风险，命中多跳路径', tags: ['ROUTE', '多跳'] },
  { id: 'B-008', question: '无风险供应商的产能情况', expected: '低风险', tags: ['DIRECT'] },
]

const benchmarkMetrics = {
  precision: 0.86,
  recall: 0.82,
  f1: 0.84,
  path_hit_rate: 0.78,
  role_block_rate: 1.0,
  risk_accuracy: 0.88,
}

const benchmarkBaseline = {
  precision: 0.71,
  recall: 0.64,
  f1: 0.67,
  path_hit_rate: 0.35,
  role_block_rate: 0.5,
  risk_accuracy: 0.75,
}

const benchmarkResults = [
  { id: 'B-001', passed: true, note: '结论与图谱路径均命中' },
  { id: 'B-002', passed: true, note: '命中备选航线建议' },
  { id: 'B-003', passed: true, note: '命中东莞工厂停线风险' },
  { id: 'B-004', passed: false, note: '风险等级判为中，期望为低' },
  { id: 'B-005', passed: true, note: '越权请求被拦截并写入审计' },
  { id: 'B-006', passed: true, note: '跨租户请求被拦截' },
  { id: 'B-007', passed: true, note: '多跳路径命中' },
  { id: 'B-008', passed: true, note: '结论命中' },
]

export async function fetchBenchmark() {
  await delay(150)
  return {
    cases: benchmarkCases,
    last_run: {
      ran_at: '2026-10-22 21:10',
      metrics: benchmarkMetrics,
      baseline: benchmarkBaseline,
      results: benchmarkResults,
    },
  }
}

export async function runBenchmark() {
  await delay(1500)
  return {
    ran_at: new Date().toLocaleString('zh-CN', { hour12: false }),
    metrics: benchmarkMetrics,
    baseline: benchmarkBaseline,
    results: benchmarkResults,
  }
}

const auditSeed = [
  ['2026-10-23 10:12:31', 'zhangsan', 'procurement', 'query', '华东精密制造停产影响', 'allowed'],
  ['2026-10-23 10:11:08', 'lisi', 'logistics', 'retrieve', '上海港拥堵周报', 'allowed'],
  ['2026-10-23 10:05:44', 'wangwu', 'finance', 'retrieve', '采购合同-2026Q4', 'blocked'],
  ['2026-10-23 09:58:12', 'zhangsan', 'procurement', 'approve', 'R-3001', 'allowed'],
  ['2026-10-23 09:52:37', 'lisi', 'logistics', 'reject', 'R-3002', 'allowed'],
  ['2026-10-23 09:40:03', 'zhaoliu', 'quality', 'upload', '东莞工厂质检报告', 'allowed'],
  ['2026-10-22 18:20:55', 'zhangsan', 'procurement', 'query', '芯片短缺影响', 'allowed'],
  ['2026-10-22 17:03:19', 'admin', 'admin', 'login', '管理后台', 'allowed'],
  ['2026-10-22 16:47:02', 'wangwu', 'finance', 'query', '付款记录', 'allowed'],
  ['2026-10-22 15:12:44', 'lisi', 'logistics', 'query', '其他租户航线数据', 'blocked'],
  ['2026-10-22 14:30:10', 'zhaoliu', 'quality', 'retrieve', '供应商质量评分', 'allowed'],
  ['2026-10-22 11:22:36', 'zhangsan', 'procurement', 'export', '审计日志', 'allowed'],
  ['2026-10-21 20:15:09', 'admin', 'admin', 'export', '用户列表', 'allowed'],
  ['2026-10-21 19:02:41', 'unknown', '', 'login', '无效密码', 'failed'],
  ['2026-10-21 16:44:27', 'wangwu', 'finance', 'reject', 'R-2997', 'allowed'],
  ['2026-10-21 10:18:52', 'lisi', 'logistics', 'query', '港口罢工路径', 'allowed'],
  ['2026-10-20 17:55:33', 'zhaoliu', 'quality', 'approve', 'R-2998', 'allowed'],
  ['2026-10-20 09:30:11', 'zhangsan', 'procurement', 'upload', '昆山工厂停产通知', 'allowed'],
]

const auditLogs = auditSeed.map((row, index) => {
  const [time, user, role, action, resource, result] = row
  return {
    id: index + 1,
    time,
    user,
    role,
    tenant: 'demo',
    action,
    resource,
    result,
    request_id: `req-${(0x7f3a2c + index * 7919).toString(16)}`,
  }
})

export async function fetchAuditLogs({
  page = 1,
  page_size = 10,
  action = '',
  result = '',
  keyword = '',
  range = [],
} = {}) {
  await delay(200)
  let items = auditLogs

  if (action) items = items.filter((log) => log.action === action)
  if (result) items = items.filter((log) => log.result === result)
  if (keyword) {
    items = items.filter(
      (log) => log.user.includes(keyword) || log.resource.includes(keyword),
    )
  }
  if (range?.length === 2) {
    const [start, end] = range
    items = items.filter((log) => {
      const day = log.time.slice(0, 10)
      return day >= start && day <= end
    })
  }

  const startIndex = (page - 1) * page_size
  return {
    items: items.slice(startIndex, startIndex + page_size),
    total: items.length,
  }
}

const adminTenants = [
  { tenant_id: 'demo', name: '演示租户', created_at: '2026-10-01', user_count: 4 },
  { tenant_id: 'acme', name: 'Acme 供应链', created_at: '2026-10-05', user_count: 1 },
]

const adminUsers = [
  { user_id: 'u-1', username: 'admin', role: 'admin', tenant_id: 'demo', status: 'active' },
  { user_id: 'u-2', username: 'zhangsan', role: 'procurement', tenant_id: 'demo', status: 'active' },
  { user_id: 'u-3', username: 'lisi', role: 'logistics', tenant_id: 'demo', status: 'active' },
  { user_id: 'u-4', username: 'wangwu', role: 'finance', tenant_id: 'demo', status: 'disabled' },
  { user_id: 'u-5', username: 'zhaoliu', role: 'quality', tenant_id: 'acme', status: 'active' },
]

const adminRoles = [
  { role: 'admin', name: '管理员', scope: '管理租户、用户、角色策略与审计', permissions: ['全部文档', '审批', '审计导出'] },
  { role: 'procurement', name: '采购', scope: '采购合同、供应商交付与风险提问', permissions: ['采购文档', '发起问答', '提交复核'] },
  { role: 'logistics', name: '物流', scope: '物流周报、航线与港口事件', permissions: ['物流文档', '发起问答'] },
  { role: 'quality', name: '质量', scope: '质检报告与供应商质量评分', permissions: ['质量文档', '发起问答'] },
  { role: 'finance', name: '财务', scope: '付款记录与供应商财务评级', permissions: ['财务文档', '发起问答'] },
]

const adminMetrics = {
  requests_today: 128,
  llm_calls: 342,
  blocked: 7,
  approval_backlog: 2,
}

const adminLogs = [
  { time: '10:12:31', level: 'INFO', message: 'POST /api/chat 完成，耗时 3.2s', request_id: 'req-7f3a2c' },
  { time: '10:05:44', level: 'WARNING', message: '越权拦截：finance 读取 procurement 文档', request_id: 'req-8b41d3' },
  { time: '09:58:12', level: 'INFO', message: '审批通过 R-3001，工作流恢复', request_id: 'req-9c22e1' },
  { time: '09:40:03', level: 'INFO', message: '文档摄取完成：东莞工厂质检报告', request_id: 'req-a13f02' },
  { time: '09:02:41', level: 'ERROR', message: '登录失败：用户 unknown', request_id: 'req-b7d90a' },
]

export async function fetchAdminData() {
  await delay(150)
  return {
    tenants: adminTenants.map((item) => ({ ...item })),
    users: adminUsers.map((item) => ({ ...item })),
    roles: adminRoles.map((item) => ({ ...item })),
    metrics: { ...adminMetrics },
    logs: adminLogs.map((item) => ({ ...item })),
  }
}

export async function createTenant({ tenant_id, name }) {
  await delay(200)
  return {
    tenant_id,
    name,
    created_at: new Date().toISOString().slice(0, 10),
    user_count: 0,
  }
}

export async function createUser({ username, role, tenant_id }) {
  await delay(200)
  return {
    user_id: `u-${Date.now()}`,
    username,
    role,
    tenant_id,
    status: 'active',
  }
}
