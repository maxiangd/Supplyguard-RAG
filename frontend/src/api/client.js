import axios from 'axios'
import { useAuthStore } from '../stores/auth'
import router from '../router'

const client = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

client.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  if (auth.tenantId) {
    config.headers['X-Tenant-ID'] = auth.tenantId
  }
  return config
})

client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore().logout()
      router.push({ name: 'login' })
    }
    return Promise.reject(error)
  },
)

export default client