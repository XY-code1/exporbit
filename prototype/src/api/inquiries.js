const API_BASE = import.meta.env?.VITE_API_BASE_URL || 'http://localhost:8010/api/v1'

async function request(path, options = {}) {
  let response
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {...(isFormData ? {} : {'Content-Type': 'application/json'}), ...(options.headers || {})},
    })
  } catch {
    throw new Error('无法连接服务器，请检查网络后重试。')
  }
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body?.error?.message || `请求失败（${response.status}）`)
  return body
}

export const inquiryApi = {
  list: ({query = '', status = ''} = {}) => {
    const params = new URLSearchParams()
    if (query) params.set('q', query)
    if (status) params.set('workflow_status', status)
    return request(`/inquiries${params.size ? `?${params}` : ''}`)
  },
  get: id => request(`/inquiries/${id}`),
  create: payload => request('/inquiries', {method: 'POST', body: JSON.stringify(payload)}),
  importFiles: files => {
    const form = new FormData()
    files.forEach(file => form.append('files', file))
    return request('/inquiries/import', {method: 'POST', body: form})
  },
  files: id => request(`/inquiries/${id}/files`),
  extract: id => request(`/inquiries/${id}/extract`, {method: 'POST'}),
  latestExtraction: id => request(`/inquiries/${id}/extractions/latest`),
  extractionHistory: id => request(`/inquiries/${id}/extractions`),
  extraction: (inquiryId, extractionId) => request(`/inquiries/${inquiryId}/extractions/${extractionId}`),
}
