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