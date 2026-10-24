import client from './client'

export function fetchDocuments() {
  return client.get('/documents')
}

export function uploadDocument({ file, allowedRoles }) {
  const form = new FormData()
  form.append('file', file)
  form.append('allowed_roles', allowedRoles.join(','))
  return client.post('/documents', form)
}

export function retryDocument(documentId) {
  return client.post(`/documents/${documentId}/retry`)
}
