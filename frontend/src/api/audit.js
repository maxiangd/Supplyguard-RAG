import client from './client'

export function fetchAuditLogs(limit = 100) {
  return client.get('/audit', { params: { limit } })
}

export function clearAuditLogs() {
  return client.delete('/audit')
}