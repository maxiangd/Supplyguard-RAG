import client from './client'

export function fetchUsers() {
  return client.get('/users')
}

export function createUser({ username, password, role }) {
  return client.post('/users', { username, password, role })
}

export function updateUser(userId, payload) {
  return client.patch(`/users/${userId}`, payload)
}

export function deleteUser(userId) {
  return client.delete(`/users/${userId}`)
}
