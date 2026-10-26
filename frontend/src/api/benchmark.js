/** Benchmark API：用例列表 + 运行评测 */
import api from './client';

// 注意：client 的 response 拦截器已自动解包 response.data，
// 这里直接返回即可，不要再取 .data
export function fetchBenchmarkCases() {
  return api.get('/benchmark/cases');
}

export function runBenchmark() {
  return api.post('/benchmark/run');
}