/** 记忆 API：短期会话 + 长期记忆 */
import api from './client'

export function getSessionHistory() {
  return api.get('/memory/session').then(r => r.data)
}

export function clearSession() {
  return api.delete('/memory/session').then(r => r.data)
}

export function listLongTermMemories(category) {
  return api.get('/memory/long-term', { params: { category } }).then(r => r.data)
}

export function createLongTermMemory(data) {
  return api.post('/memory/long-term', data).then(r => r.data)
}

export function getLongTermMemory(memoryId) {
  return api.get(`/memory/long-term/${memoryId}`).then(r => r.data)
}

export function updateLongTermMemory(memoryId, data) {
  return api.patch(`/memory/long-term/${memoryId}`, data).then(r => r.data)
}

export function deleteLongTermMemory(memoryId) {
  return api.delete(`/memory/long-term/${memoryId}`).then(r => r.data)
}