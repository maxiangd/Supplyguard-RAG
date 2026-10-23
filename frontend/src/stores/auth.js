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

  const isLoggedIn = computed(() => Boolean(token.value))
  const role = computed(() => user.value?.role ?? '')

  async function login({ username, password }) {
    const data = await client.post('/auth/login', { username, password })

    token.value = data.access_token
    user.value = data.user

    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
  }

  async function fetchMe() {
    const data = await client.get('/auth/me')
    user.value = data
    localStorage.setItem('user', JSON.stringify(data))
  }

  function logout() {
    token.value = ''
    user.value = null

    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return { token, user, isLoggedIn, role, login, fetchMe, logout }
})