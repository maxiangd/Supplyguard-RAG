import client from './client'

export function fetchApprovals() {
  return client.get('/approvals')
}

export function fetchApproval(approvalId) {
  return client.get(`/approvals/${approvalId}`)
}

export function decideApproval(approvalId, action, comment) {
  return client.post(`/approvals/${approvalId}/decide`, {
    action,
    comment,
  })
}