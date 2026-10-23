import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

client.interceptors.request.use((config) => {
  // 从 localStorage 读取，避免与 Pinia store 形成循环依赖
  const token = localStorage.getItem('token')

  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    if (error.response?.status === 401) {
      // 动态导入，避免 client → store/router 的静态循环依赖
      const [{ useAuthStore }, { default: router }] = await Promise.all([
        import('../stores/auth'),
        import('../router'),
      ])
      useAuthStore().logout()
      router.push({ name: 'login' })
    }
    return Promise.reject(error)
  },
)

export default client