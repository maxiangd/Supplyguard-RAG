import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import client from '../api/client'

function readUser() {
  const raw = localStorage.getItem('user')
  return raw ? JSON.parse(raw) : null
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(readUser())
  const tenantId = ref(localStorage.getItem('tenant_id') || '')

  const isLoggedIn = computed(() => Boolean(token.value))
  const role = computed(() => user.value?.role ?? '')

  async function login({ username, password, tenant }) {
    const data = await client.post('/auth/login', {
      username,
      password,
      tenant_id: tenant || null,
    })

    token.value = data.access_token
    user.value = data.user
    tenantId.value = data.tenant_id

    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    localStorage.setItem('tenant_id', data.tenant_id)
  }

  async function fetchMe() {
    const data = await client.get('/auth/me')
    user.value = data
    localStorage.setItem('user', JSON.stringify(data))
  }

  function logout() {
    token.value = ''
    user.value = null
    tenantId.value = ''

    localStorage.removeItem('token')
    localStorage.removeItem('user')
    localStorage.removeItem('tenant_id')
  }

  return { token, user, tenantId, isLoggedIn, role, login, fetchMe, logout }
})