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

export function deleteDocument(documentId) {
  return client.delete(`/documents/${documentId}`)
}

export function updateDocumentRoles(documentId, allowedRoles) {
  return client.patch(`/documents/${documentId}/roles`, {
    allowed_roles: allowedRoles,
  })
}

export function fetchDocumentChunks(documentId) {
  return client.get(`/documents/${documentId}/chunks`)
}
