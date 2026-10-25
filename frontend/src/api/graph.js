import client from './client'

// 当前角色可见的供应链子图
export function fetchGraphOverview() {
  return client.get('/graph/overview')
}

// 按问题或实体做多跳影响分析
export function analyzeImpact({ question, entityId, maxHops = 3 }) {
  return client.post('/graph/impact', {
    question,
    entity_id: entityId,
    max_hops: maxHops,
  })
}
