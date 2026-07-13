const API_BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

export async function uploadScreenshots(files) {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  return request('/upload', { method: 'POST', body: form })
}

export async function uploadResume(file) {
  const form = new FormData()
  form.append('file', file)
  return request('/upload-resume', { method: 'POST', body: form })
}

export async function listJobs() {
  return request('/jobs')
}

export async function extractJob(jobId) {
  return request(`/jobs/${jobId}/extract`, { method: 'POST' })
}

export async function generateEmail(jobId, sender, template) {
  return request(`/jobs/${jobId}/generate-email`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sender, template }),
  })
}

export async function processBatch(payload, jobIds) {
  const params = jobIds?.length ? `?${jobIds.map((id) => `job_ids=${id}`).join('&')}` : ''
  return request(`/process-batch${params}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function sendBatch(payload) {
  return request('/send-batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function sendJobEmail(payload) {
  return request(`/jobs/${payload.job_id}/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function deleteJob(jobId) {
  return request(`/jobs/${jobId}`, { method: 'DELETE' })
}

export async function fixJobEmail(jobId, data) {
  return request(`/jobs/${jobId}/fix-email`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function healthCheck() {
  return request('/health')
}

export async function fetchAppConfig() {
  return request('/config')
}

export async function findLinkedInJobs(roles, maxResults = 30) {
  return request('/find-jobs/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ roles, max_results: maxResults }),
  })
}

export async function importLinkedInPosts(posts) {
  return request('/find-jobs/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ posts }),
  })
}
