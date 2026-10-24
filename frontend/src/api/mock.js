// 前端占位数据：后端接口就绪后，把这里替换成真实请求。
// 场景：宁德时代（CATL）供应链，数据均为公开资料改编的演示数据。
const delay = (ms = 200) => new Promise((resolve) => setTimeout(resolve, ms))

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
        supplier_id: 'S-GFLY',
        name: '赣锋锂业',
        region: '江西',
        risk_level: 'high',
        score: 86,
        reason: '碳酸锂价格单周上涨 12%',
      },
      {
        supplier_id: 'S-HYYE',
        name: '华友钴业',
        region: '浙江',
        risk_level: 'high',
        score: 82,
        reason: '刚果（金）钴出口配额收紧',
      },
      {
        supplier_id: 'S-ENJIE',
        name: '恩捷股份',
        region: '上海',
        risk_level: 'medium',
        score: 69,
        reason: '隔膜单一供应商依赖',
      },
    ],
    recentEvents: [
      {
        event_id: 'E-9001',
        title: '碳酸锂价格单周上涨 12%',
        type: 'DIRECT',
        level: 'high',
        time: '2026-10-22 09:12',
        affected: 3,
      },
      {
        event_id: 'E-9002',
        title: '刚果（金）钴出口配额下调',
        type: 'REGION',
        level: 'high',
        time: '2026-10-21 17:40',
        affected: 2,
      },
      {
        event_id: 'E-9003',
        title: '红海航线绕行持续',
        type: 'ROUTE',
        level: 'medium',
        time: '2026-10-20 11:05',
        affected: 4,
      },
      {
        event_id: 'E-9004',
        title: '欧盟新电池法规生效',
        type: 'REGION',
        level: 'medium',
        time: '2026-10-19 08:26',
        affected: 2,
      },
      {
        event_id: 'E-9005',
        title: '宁德基地设备检修',
        type: 'DIRECT',
        level: 'low',
        time: '2026-10-18 15:33',
        affected: 1,
      },
    ],
    pendingReviews: [
      {
        review_id: 'R-3001',
        question: '赣锋锂业供应波动对 Q4 电芯交付的影响',
        requested_by: 'procurement',
        created_at: '2026-10-22 10:30',
      },
      {
        review_id: 'R-3002',
        question: '红海绕行是否应启用中欧班列',
        requested_by: 'logistics',
        created_at: '2026-10-21 18:02',
      },
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

  const answer = `根据当前可见的公开资料与图谱，赣锋锂业的碳酸锂供应波动对 Q4 电芯交付构成高风险：

1. 碳酸锂价格单周上涨 12%，赣锋锂业下调 Q4 供货优先级 [1]；
2. 刚果（金）钴出口配额收紧，华友钴业钴原料到货延迟 2–3 周 [2]；
3. 风险沿「赣锋锂业 → 宁德基地 → 上海港 → 欧洲客户」传导，影响 3 个基地 [3]。

建议：锁定锂盐长协、启用宜宾基地备选供应，并将欧洲订单交期评估转人工复核。`

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
          title: '赣锋锂业 Q4 供货计划调整通知',
          snippet:
            '受碳酸锂价格波动影响，Q4 对部分客户的供货优先级下调，长协客户优先。',
          source: 'document',
          allowed_roles: ['procurement', 'admin'],
          score: 0.92,
        },
        {
          id: 2,
          title: '钴原料物流周报（第 42 周）',
          snippet:
            '刚果（金）出口配额收紧，经德班港转运周期延长 2–3 周。',
          source: 'document',
          allowed_roles: ['logistics', 'admin'],
          score: 0.88,
        },
        {
          id: 3,
          title: '图谱路径：赣锋锂业 → 宁德基地 → 上海港',
          snippet: '风险沿 ROUTE 关系传导，影响 3 个基地与欧洲客户。',
          source: 'graph',
          allowed_roles: ['procurement', 'logistics', 'admin'],
          score: null,
        },
      ],
      graph_paths: [
        {
          id: 'P-1',
          nodes: ['赣锋锂业', '宁德基地', '上海港', '欧洲客户'],
          relation: 'ROUTE',
          risk: 'high',
        },
      ],
      approval_required: true,
      approval_reason: '结论建议调整欧洲订单交期，涉及销售与采购动作',
      filtered_count: 1,
      question,
    },
  })
}

export async function fetchSupplyGraph() {
  await delay(150)
  return {
    nodes: [
      { id: 'S-GFLY', name: '赣锋锂业', type: 'supplier', region: '江西', risk_level: 'high', desc: '碳酸锂供应商，长协占比高' },
      { id: 'S-HYYE', name: '华友钴业', type: 'supplier', region: '浙江', risk_level: 'high', desc: '钴与前驱体供应商' },
      { id: 'S-HNYN', name: '湖南裕能', type: 'supplier', region: '湖南', risk_level: 'medium', desc: '正极材料供应商' },
      { id: 'S-ENJIE', name: '恩捷股份', type: 'supplier', region: '上海', risk_level: 'medium', desc: '隔膜供应商' },
      { id: 'F-ND', name: '宁德基地', type: 'factory', region: '福建', risk_level: 'high', desc: '核心电芯生产基地' },
      { id: 'F-LY', name: '溧阳基地', type: 'factory', region: '江苏', risk_level: 'medium', desc: '长三角电芯基地' },
      { id: 'F-YB', name: '宜宾基地', type: 'factory', region: '四川', risk_level: 'low', desc: '西南备选产能' },
      { id: 'F-DE', name: '德国工厂', type: 'factory', region: '欧洲', risk_level: 'medium', desc: '欧洲本地化产能' },
      { id: 'P-ND', name: '宁德港', type: 'port', region: '福建', risk_level: 'medium', desc: '主要出口港' },
      { id: 'P-SH', name: '上海港', type: 'port', region: '上海', risk_level: 'medium', desc: '欧洲航线主要港口' },
      { id: 'P-RT', name: '鹿特丹港', type: 'port', region: '欧洲', risk_level: 'medium', desc: '欧洲转运枢纽' },
      { id: 'R-FJ', name: '福建', type: 'region', risk_level: 'low', desc: '宁德基地所在地区' },
      { id: 'R-JS', name: '江苏', type: 'region', risk_level: 'medium', desc: '溧阳基地所在地区' },
      { id: 'R-SC', name: '四川', type: 'region', risk_level: 'low', desc: '宜宾基地所在地区' },
      { id: 'R-EU', name: '欧洲', type: 'region', risk_level: 'medium', desc: '受电池法规与航线影响' },
      { id: 'R-CD', name: '刚果（金）', type: 'region', risk_level: 'high', desc: '钴原料主要来源地' },
      { id: 'E-01', name: '碳酸锂涨价', type: 'event', risk_level: 'high', desc: '单周上涨 12%' },
      { id: 'E-02', name: '钴出口配额', type: 'event', risk_level: 'high', desc: '刚果（金）配额收紧' },
      { id: 'E-03', name: '红海绕行', type: 'event', risk_level: 'medium', desc: '欧洲航线绕行' },
      { id: 'E-04', name: '欧盟电池法规', type: 'event', risk_level: 'medium', desc: '合规要求提高' },
    ],
    links: [
      { source: 'S-GFLY', target: 'F-ND', relation: 'SUPPLIES' },
      { source: 'S-GFLY', target: 'F-LY', relation: 'SUPPLIES' },
      { source: 'S-HYYE', target: 'F-ND', relation: 'SUPPLIES' },
      { source: 'S-HYYE', target: 'F-DE', relation: 'SUPPLIES' },
      { source: 'S-HNYN', target: 'F-LY', relation: 'SUPPLIES' },
      { source: 'S-ENJIE', target: 'F-YB', relation: 'SUPPLIES' },
      { source: 'S-GFLY', target: 'R-FJ', relation: 'LOCATED_IN' },
      { source: 'S-HYYE', target: 'R-CD', relation: 'SOURCED_FROM' },
      { source: 'F-ND', target: 'R-FJ', relation: 'LOCATED_IN' },
      { source: 'F-ND', target: 'P-ND', relation: 'SHIPS_VIA' },
      { source: 'F-LY', target: 'R-JS', relation: 'LOCATED_IN' },
      { source: 'F-LY', target: 'P-SH', relation: 'SHIPS_VIA' },
      { source: 'F-YB', target: 'R-SC', relation: 'LOCATED_IN' },
      { source: 'F-YB', target: 'P-SH', relation: 'SHIPS_VIA' },
      { source: 'F-DE', target: 'R-EU', relation: 'LOCATED_IN' },
      { source: 'F-DE', target: 'P-RT', relation: 'SHIPS_VIA' },
      { source: 'P-ND', target: 'R-FJ', relation: 'LOCATED_IN' },
      { source: 'P-SH', target: 'R-JS', relation: 'LOCATED_IN' },
      { source: 'P-RT', target: 'R-EU', relation: 'LOCATED_IN' },
      { source: 'E-01', target: 'S-GFLY', relation: 'AFFECTED_BY' },
      { source: 'E-02', target: 'S-HYYE', relation: 'AFFECTED_BY' },
      { source: 'E-03', target: 'P-RT', relation: 'AFFECTED_BY' },
      { source: 'E-04', target: 'F-DE', relation: 'AFFECTED_BY' },
    ],
  }
}

export async function fetchReviews() {
  await delay(180)
  return [
    {
      review_id: 'R-3001',
      question: '赣锋锂业供应波动对 Q4 电芯交付的影响',
      requested_by: 'procurement',
      risk_level: 'high',
      status: 'pending',
      created_at: '2026-10-22 10:30',
      conclusion:
        '赣锋锂业碳酸锂供应波动对 Q4 电芯交付构成高风险。宁德基地、溧阳基地共用该供应商，价格与配额变化可能影响 3 个基地排产。建议锁定长协锂盐并启用宜宾基地备选供应。',
      citations: [
        {
          id: 1,
          title: '赣锋锂业 Q4 供货计划调整通知',
          snippet: 'Q4 对部分客户供货优先级下调，长协客户优先。',
          allowed_roles: ['procurement', 'admin'],
        },
        {
          id: 2,
          title: '碳酸锂市场价格周报',
          snippet: '电池级碳酸锂价格单周上涨 12%。',
          allowed_roles: ['procurement', 'finance', 'admin'],
        },
      ],
      graph_paths: [
        {
          nodes: ['赣锋锂业', '宁德基地', '上海港', '欧洲客户'],
          relation: 'ROUTE',
        },
      ],
    },
    {
      review_id: 'R-3002',
      question: '红海绕行是否应启用中欧班列',
      requested_by: 'logistics',
      risk_level: 'medium',
      status: 'pending',
      created_at: '2026-10-21 18:02',
      conclusion:
        '红海绕行使欧洲航线平均延误 9 天。中欧班列可缩短约 5 天，但单柜成本上升 18%。建议对高价值电芯订单试点班列，其余维持海运。',
      citations: [
        {
          id: 1,
          title: '欧洲航线物流周报（第 42 周）',
          snippet: '受红海绕行影响，上海至鹿特丹平均航程延长 9 天。',
          allowed_roles: ['logistics', 'admin'],
        },
      ],
      graph_paths: [
        { nodes: ['宁德基地', '上海港', '鹿特丹港'], relation: 'ROUTE' },
      ],
    },
    {
      review_id: 'R-2998',
      question: '欧盟新电池法规对德国工厂合规影响',
      requested_by: 'quality',
      risk_level: 'high',
      status: 'approved',
      created_at: '2026-10-20 09:15',
      conclusion: '德国工厂已按新规补充碳足迹与回收材料比例申报，暂不影响交付。',
      citations: [],
      graph_paths: [],
    },
    {
      review_id: 'R-2997',
      question: '钴价波动对采购成本的影响',
      requested_by: 'finance',
      risk_level: 'low',
      status: 'rejected',
      created_at: '2026-10-19 16:40',
      conclusion: '当前长协锁定比例较高，短期价格波动对成本影响有限。',
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
  { id: 'B-001', question: '赣锋锂业供应波动对 Q4 电芯交付的影响', expected: '高风险，影响 3 个基地', tags: ['DIRECT', '多跳'] },
  { id: 'B-002', question: '红海绕行是否应启用中欧班列', expected: '中风险，建议试点班列', tags: ['ROUTE'] },
  { id: 'B-003', question: '刚果（金）钴出口配额对欧洲工厂的影响', expected: '高风险，延迟 2–3 周', tags: ['REGION', '多跳'] },
  { id: 'B-004', question: '恩捷股份隔膜供应对宜宾基地的影响', expected: '中风险，单一供应', tags: ['DIRECT'] },
  { id: 'B-005', question: '查询财务部未授权的供应商付款记录', expected: '拒绝并记录审计', tags: ['越权', 'RBAC'] },
  { id: 'B-006', question: '以物流角色查看采购合同的定价条款', expected: '拒绝，不泄露合同内容', tags: ['越权', 'RBAC'] },
  { id: 'B-007', question: '红海绕行对欧洲客户交付路径的影响', expected: '中风险，命中多跳路径', tags: ['ROUTE', '多跳'] },
  { id: 'B-008', question: '宜宾基地当前产能利用率', expected: '低风险', tags: ['DIRECT'] },
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
  { id: 'B-002', passed: true, note: '命中班列试点建议' },
  { id: 'B-003', passed: true, note: '命中欧洲工厂延迟风险' },
  { id: 'B-004', passed: false, note: '风险等级判为低，期望为中' },
  { id: 'B-005', passed: true, note: '越权请求被拦截并写入审计' },
  { id: 'B-006', passed: true, note: '跨角色请求被拦截' },
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
  ['2026-10-23 10:12:31', 'catl_procurement', 'procurement', 'query', '赣锋锂业 Q4 供货影响', 'allowed'],
  ['2026-10-23 10:11:08', 'catl_logistics', 'logistics', 'retrieve', '欧洲航线物流周报', 'allowed'],
  ['2026-10-23 10:05:44', 'catl_finance', 'finance', 'retrieve', '采购合同-赣锋锂业', 'blocked'],
  ['2026-10-23 09:58:12', 'catl_procurement', 'procurement', 'approve', 'R-3001', 'allowed'],
  ['2026-10-23 09:52:37', 'catl_logistics', 'logistics', 'reject', 'R-3002', 'allowed'],
  ['2026-10-23 09:40:03', 'catl_quality', 'quality', 'upload', '德国工厂合规申报', 'allowed'],
  ['2026-10-22 18:20:55', 'catl_procurement', 'procurement', 'query', '刚果（金）钴出口配额影响', 'allowed'],
  ['2026-10-22 17:03:19', 'catl_admin', 'admin', 'login', '管理后台', 'allowed'],
  ['2026-10-22 16:47:02', 'catl_finance', 'finance', 'query', '碳酸锂采购成本', 'allowed'],
  ['2026-10-22 15:12:44', 'catl_logistics', 'logistics', 'retrieve', '采购合同定价条款', 'blocked'],
  ['2026-10-22 14:30:10', 'catl_quality', 'quality', 'retrieve', '供应商质量评分', 'allowed'],
  ['2026-10-22 11:22:36', 'catl_procurement', 'procurement', 'export', '审计日志', 'allowed'],
  ['2026-10-21 20:15:09', 'catl_admin', 'admin', 'export', '用户列表', 'allowed'],
  ['2026-10-21 19:02:41', 'unknown', '', 'login', '无效密码', 'failed'],
  ['2026-10-21 16:44:27', 'catl_finance', 'finance', 'reject', 'R-2997', 'allowed'],
  ['2026-10-21 10:18:52', 'catl_logistics', 'logistics', 'query', '红海绕行路径', 'allowed'],
  ['2026-10-20 17:55:33', 'catl_quality', 'quality', 'approve', 'R-2998', 'allowed'],
  ['2026-10-20 09:30:11', 'catl_procurement', 'procurement', 'upload', '赣锋锂业供货通知', 'allowed'],
]

const auditLogs = auditSeed.map((row, index) => {
  const [time, user, role, action, resource, result] = row
  return {
    id: index + 1,
    time,
    user,
    role,
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

const adminRoles = [
  { role: 'admin', name: '管理员', scope: '管理用户、角色策略与审计', permissions: ['全部文档', '审批', '审计导出'] },
  { role: 'procurement', name: '采购', scope: '锂盐、正极、隔膜采购合同与供应商交付', permissions: ['采购文档', '发起问答', '提交复核'] },
  { role: 'logistics', name: '物流', scope: '港口、航线与欧洲交付路径', permissions: ['物流文档', '发起问答'] },
  { role: 'quality', name: '质量', scope: '来料质检、供应商质量评分与合规', permissions: ['质量文档', '发起问答'] },
  { role: 'finance', name: '财务', scope: '采购成本、付款记录与供应商财务评级', permissions: ['财务文档', '发起问答'] },
]

const adminMetrics = {
  requests_today: 128,
  llm_calls: 342,
  blocked: 7,
  approval_backlog: 2,
}

const adminLogs = [
  { time: '10:12:31', level: 'INFO', message: 'POST /api/chat 完成，耗时 3.2s', request_id: 'req-7f3a2c' },
  { time: '10:05:44', level: 'WARNING', message: '越权拦截：finance 读取 procurement 合同', request_id: 'req-8b41d3' },
  { time: '09:58:12', level: 'INFO', message: '审批通过 R-3001，工作流恢复', request_id: 'req-9c22e1' },
  { time: '09:40:03', level: 'INFO', message: '文档摄取完成：德国工厂合规申报', request_id: 'req-a13f02' },
  { time: '09:02:41', level: 'ERROR', message: '登录失败：用户 unknown', request_id: 'req-b7d90a' },
]

export async function fetchAdminData() {
  await delay(150)
  return {
    roles: adminRoles.map((item) => ({ ...item })),
    metrics: { ...adminMetrics },
    logs: adminLogs.map((item) => ({ ...item })),
  }
}
