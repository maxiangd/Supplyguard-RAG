import client from './client'

export function fetchChatModels() {
  return client.get('/chat/models')
}

export function askQuestion({ question, model, topK }) {
  return client.post('/chat/answer', {
    question,
    model,
    top_k: topK,
  })
}

// EventSource 不能带 Authorization 头，所以用 fetch 读取 SSE 流
export async function streamAnswer({ question, model, onEvent }) {
  const response = await fetch('/api/chat/answer/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${localStorage.getItem('token')}`,
    },
    body: JSON.stringify({ question, model }),
  })

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail ?? '请求失败')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const chunks = buffer.split('\n\n')
    buffer = chunks.pop()
    for (const chunk of chunks) {
      const line = chunk.split('\n').find((item) => item.startsWith('data: '))
      if (line) onEvent(JSON.parse(line.slice(6)))
    }
  }
}
