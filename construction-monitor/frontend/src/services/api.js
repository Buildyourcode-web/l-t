const BASE_URL = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  getDashboard: () => request('/dashboard'),
  getCameras: () => request('/cameras'),
  getViolations: (params = {}) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => v != null && q.set(k, v))
    return request(`/violations?${q}`)
  },
  getLatestImages: (limit = 20) => request(`/latest-images?limit=${limit}`),
  getSystemHealth: () => request('/health'),
  listReports: () => request('/reports/list'),
  generateReport: (date) => request(`/reports/generate?report_date=${date}`, { method: 'POST' }),
  downloadPdf: (date) => `/api/reports/download/pdf?report_date=${date}`,
  downloadExcel: (date) => `/api/reports/download/excel?report_date=${date}`,
}
