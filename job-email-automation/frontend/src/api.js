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

export async function saveJobDraft(jobId, draft) {
  return request(`/jobs/${jobId}/draft`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(draft),
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

export async function findLinkedInJobs(roles, maxResults = 30, timePeriod = 'week', experienceRange = '2-4') {
  return request('/find-jobs/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      roles,
      max_results: maxResults,
      time_period: timePeriod,
      experience_range: experienceRange,
    }),
  })
}

export async function importLinkedInPosts(posts, options = {}) {
  return request('/find-jobs/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      posts,
      auto_generate: options.autoGenerate !== false,
      sender: options.sender,
      template: options.template,
      candidate: options.candidate,
    }),
  })
}

export async function pasteLinkedInPost(payload) {
  return request('/find-jobs/paste', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function enrichLinkedInPost(url, snippet = '') {
  return request('/find-jobs/enrich', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, snippet }),
  })
}

export async function fetchAnalytics() {
  return request('/analytics')
}

export async function updateJobOutcome(jobId, outcome, notes) {
  return request(`/jobs/${jobId}/outcome`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ outcome, notes }),
  })
}

export async function fetchScheduler() {
  return request('/scheduler')
}

export async function updateScheduler(data) {
  return request('/scheduler', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function runSchedulerNow() {
  return request('/scheduler/run-now', { method: 'POST' })
}

export async function fetchResumeProfiles() {
  return request('/resumes/profiles')
}

export async function saveResumeProfiles(profiles) {
  return request('/resumes/profiles', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profiles }),
  })
}

export async function suggestResume(role) {
  const q = encodeURIComponent(role || '')
  return request(`/resumes/suggest?role=${q}`)
}

export async function fetchRoleTemplates() {
  return request('/templates/roles')
}

export async function saveRoleTemplates(templates) {
  return request('/templates/roles', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ templates }),
  })
}
