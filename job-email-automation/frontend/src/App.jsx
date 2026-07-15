import { useCallback, useEffect, useState } from 'react'
import {
  healthCheck,
  listJobs,
  processBatch,
  uploadResume,
  uploadScreenshots,
  deleteJob,
  sendJobEmail,
  fixJobEmail,
  fetchAppConfig,
} from './api'
import ScreenshotUpload from './components/ScreenshotUpload'
import FindJobs from './components/FindJobs'
import TrackerPanel from './components/TrackerPanel'
import JobList from './components/JobList'
import SettingsPanel from './components/SettingsPanel'
import EmailPreviewModal from './components/EmailPreviewModal'

const DEFAULT_TEMPLATE = {
  subject_template: 'Application for {role} at {company}',
  body_template: `Hi {recruiter_name},

I came across your LinkedIn post regarding the opening for the {role} role at {company} and found the opportunity closely aligned with my skills and experience.

{experience_summary}

Please find my resume attached for your reference. I would appreciate the opportunity to discuss how my experience can contribute to your team.

Looking forward to hearing from you.

Thanks & Regards,
{sender_name}`,
}

const EMPTY_SETTINGS = {
  sender: { name: '', email: '', phone: '' },
  candidate: {
    current_role: '',
    years_experience: '',
    key_skills: '',
    experience_summary: '',
  },
  smtp: { host: 'smtp.gmail.com', port: 587, user: '', password: '', use_tls: true },
  template: DEFAULT_TEMPLATE,
  resumeFilename: null,
  resumeDisplayName: null,
  fromEnv: false,
  configured: { smtp: false, sender: false, resume: false, all_ready: false },
}

export default function App() {
  const [jobs, setJobs] = useState([])
  const [settings, setSettings] = useState(EMPTY_SETTINGS)
  const [configLoaded, setConfigLoaded] = useState(false)
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [message, setMessage] = useState(null)
  const [apiStatus, setApiStatus] = useState(null)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewJobId, setPreviewJobId] = useState(null)
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [activeTab, setActiveTab] = useState('upload') // upload | find | tracker

  const saveSettings = useCallback((next) => {
    setSettings(next)
  }, [])

  const loadEnvConfig = useCallback(async () => {
    try {
      const cfg = await fetchAppConfig()
      setSettings({
        sender: cfg.sender,
        candidate: cfg.candidate,
        smtp: cfg.smtp,
        template: cfg.template,
        resumeFilename: cfg.resume_filename,
        resumeDisplayName: cfg.resume_display_name,
        fromEnv: true,
        configured: cfg.configured,
      })
      setConfigLoaded(true)
    } catch (e) {
      console.error('Failed to load .env config:', e)
      setConfigLoaded(true)
    }
  }, [])

  const refreshJobs = useCallback(async () => {
    try {
      const data = await listJobs()
      const loaded = data.jobs || []
      setJobs(loaded)
      setSelectedIds((prev) => {
        const next = new Set(prev)
        loaded.forEach((j) => {
          if (j.status !== 'sent' && !next.has(j.id)) {
            next.add(j.id)
          }
        })
        return next
      })
    } catch (e) {
      console.error(e)
    }
  }, [])

  useEffect(() => {
    loadEnvConfig()
    refreshJobs()
    healthCheck().then(setApiStatus).catch(() => setApiStatus({ status: 'error' }))
  }, [refreshJobs, loadEnvConfig])

  // Keep jobs in sync with backend (survives restarts)
  useEffect(() => {
    const interval = setInterval(refreshJobs, 10000)
    return () => clearInterval(interval)
  }, [refreshJobs])

  const showMessage = (text, type = 'info') => {
    setMessage({ text, type })
    setTimeout(() => setMessage(null), 5000)
  }

  const toggleSelect = useCallback((jobId) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(jobId)) next.delete(jobId)
      else next.add(jobId)
      return next
    })
  }, [])

  const selectAll = useCallback((ids) => {
    setSelectedIds(new Set(ids))
  }, [])

  const handleImportPosts = (result) => {
    const importedJobs = result?.jobs || (Array.isArray(result) ? result : [])
    const generated = result?.generated ?? importedJobs.filter((j) => j.status === 'email_generated').length
    const skippedUrl = result?.skipped_duplicate_url || 0
    const skippedEmail = result?.skipped_duplicate_email || 0

    if (importedJobs.length === 0) {
      const skipMsg = [
        skippedUrl ? `${skippedUrl} duplicate URL` : null,
        skippedEmail ? `${skippedEmail} duplicate email` : null,
      ].filter(Boolean).join(', ')
      showMessage(skipMsg ? `Nothing new imported (${skipMsg})` : 'Nothing imported', 'warning')
      return
    }

    setJobs((prev) => {
      const existing = new Set(prev.map((j) => j.id))
      const fresh = importedJobs.filter((j) => !existing.has(j.id))
      return [...prev, ...fresh]
    })
    setSelectedIds((prev) => {
      const next = new Set(prev)
      importedJobs.forEach((j) => next.add(j.id))
      return next
    })
    // Stay on Find tab so remaining search results stay visible

    const parts = [`Imported ${importedJobs.length}`]
    if (generated) parts.push(`${generated} email(s) ready`)
    if (skippedUrl) parts.push(`${skippedUrl} URL skipped`)
    if (skippedEmail) parts.push(`${skippedEmail} email skipped`)
    showMessage(parts.join(' · '), 'success')

    if (generated > 0) {
      setPreviewJobId(null)
      setPreviewOpen(true)
    }
  }

  const handleUpload = async (files) => {
    setLoading(true)
    try {
      const result = await uploadScreenshots(files)
      const newJobs = (result.jobs || []).map((j) => ({ ...j, has_screenshot: true }))
      setJobs((prev) => [...prev, ...newJobs])
      setSelectedIds((prev) => {
        const next = new Set(prev)
        newJobs.forEach((j) => next.add(j.id))
        return next
      })
      showMessage(`Uploaded ${result.count} screenshot(s)`, 'success')
    } catch (e) {
      showMessage(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleResumeUpload = async (file) => {
    setLoading(true)
    try {
      const result = await uploadResume(file)
      saveSettings({
        ...settings,
        resumeFilename: result.filename,
        resumeDisplayName: result.original_name,
      })
      showMessage('Resume uploaded', 'success')
    } catch (e) {
      showMessage(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleProcessAll = async () => {
    if (!settings.configured?.sender && !settings.sender.email) {
      showMessage('Set SENDER_EMAIL in backend/.env', 'error')
      return
    }
    if (!settings.configured?.resume && !settings.resumeFilename) {
      showMessage('Set DEFAULT_RESUME_PATH in backend/.env or upload resume', 'error')
      return
    }
    if (jobs.length === 0) {
      showMessage('Upload screenshots first', 'error')
      return
    }

    const toProcess = [...selectedIds].filter((id) => {
      const job = jobs.find((j) => j.id === id)
      return job && job.status !== 'sent'
    })

    if (toProcess.length === 0) {
      showMessage('Select at least one job that is not already sent', 'error')
      return
    }

    setLoading(true)
    try {
      const result = await processBatch(
        {
          sender: settings.sender,
          candidate: settings.candidate || {},
          smtp: settings.smtp,
          template: settings.template,
          auto_send: false,
          resume_filename: settings.resumeFilename,
        },
        toProcess,
      )
      setJobs((prev) => {
        const updated = new Map((result.jobs || []).map((j) => [j.id, j]))
        return prev.map((j) => updated.get(j.id) || j)
      })
      const ready = result.jobs.filter((j) => j.status === 'email_generated' && j.email?.to_email)
      const failed = result.jobs.filter((j) => j.status === 'failed').length
      if (ready.length > 0) {
        setPreviewJobId(null)
        setPreviewOpen(true)
        showMessage(`${ready.length} email(s) ready for your review`, 'success')
      } else {
        showMessage(`Processed ${result.processed} jobs — ${failed} failed`, failed ? 'warning' : 'success')
      }
    } catch (e) {
      showMessage(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleApproveAndSend = async (jobId, draft) => {
    if (!settings.configured?.smtp && (!settings.smtp.user || !settings.smtp.password)) {
      showMessage('Set SMTP_USER and SMTP_PASSWORD in backend/.env', 'error')
      return
    }

    setSending(true)
    try {
      const updated = await sendJobEmail({
        job_id: jobId,
        sender: settings.sender,
        smtp: settings.smtp,
        resume_filename: settings.resumeFilename,
        subject: draft.subject,
        body: draft.body,
        to_email: draft.to_email,
      })
      setJobs((prev) => prev.map((j) => (j.id === jobId ? updated : j)))
      showMessage(`Email sent to ${draft.to_email}`, 'success')
    } catch (e) {
      const msg = e.message?.includes('not found') || e.message?.includes('404')
        ? 'Session expired — re-upload screenshots and click Extract & Generate again.'
        : e.message
      showMessage(msg, 'error')
      // Refresh so failed status + saved draft load for Retry
      await refreshJobs()
      throw e
    } finally {
      setSending(false)
    }
  }

  const openPreview = (jobId = null) => {
    const ready = jobs.filter((j) =>
      (j.status === 'email_generated' || j.status === 'failed')
      && (j.email?.to_email || j.email_ai?.to_email),
    )
    if (ready.length === 0) {
      showMessage('No emails to preview. Run Extract & Generate first.', 'error')
      return
    }
    setPreviewJobId(jobId)
    setPreviewOpen(true)
  }

  const handleFixEmail = async (jobId, data) => {
    try {
      const fixed = await fixJobEmail(jobId, data)
      const result = await processBatch(
        {
          sender: settings.sender,
          candidate: settings.candidate || {},
          smtp: settings.smtp,
          template: settings.template,
          auto_send: false,
          resume_filename: settings.resumeFilename,
        },
        [jobId],
      )
      const updated = result.jobs[0] || fixed
      setJobs((prev) => prev.map((j) => (j.id === jobId ? updated : j)))
      showMessage('Email added — click Review & Send to preview', 'success')
    } catch (e) {
      showMessage(e.message, 'error')
    }
  }

  const handleDelete = async (jobId) => {
    try {
      await deleteJob(jobId)
      setJobs((prev) => prev.filter((j) => j.id !== jobId))
      setSelectedIds((prev) => {
        const next = new Set(prev)
        next.delete(jobId)
        return next
      })
    } catch (e) {
      showMessage(e.message, 'error')
    }
  }

  return (
    <div style={styles.app}>
      <header style={styles.header}>
        <div>
          <h1 style={styles.title}>Job Email Automation</h1>
          <p style={styles.subtitle}>
            Upload LinkedIn/Naukri screenshots → extract details → send tailored applications
          </p>
        </div>
        <div style={styles.headerActions}>
          {settings.configured?.all_ready && (
            <span style={{
              ...styles.apiBadge,
              background: '#14532d',
              color: '#4ade80',
            }}>
              Config Ready
            </span>
          )}
          {apiStatus && (
            <span style={{
              ...styles.apiBadge,
              background: apiStatus.ai_ready ? '#14532d' : '#422006',
              color: apiStatus.ai_ready ? '#4ade80' : '#fbbf24',
            }}
            title={apiStatus.ai_ready
              ? `Ollama ready (${apiStatus.vision_model})`
              : apiStatus.ollama_running
                ? 'Ollama running — pull required models'
                : 'Start Ollama: ollama serve'}
            >
              {apiStatus.ai_ready ? 'Ollama Ready' : apiStatus.ollama_running ? 'Models Missing' : 'Ollama Offline'}
            </span>
          )}
        </div>
      </header>

      {message && (
        <div style={{
          ...styles.toast,
          background: message.type === 'error' ? '#450a0a' : message.type === 'warning' ? '#422006' : '#14532d',
          color: message.type === 'error' ? '#f87171' : message.type === 'warning' ? '#fbbf24' : '#4ade80',
        }}>
          {message.text}
        </div>
      )}

      <div style={styles.layout}>
        <aside style={styles.sidebar}>
          <SettingsPanel
            settings={settings}
            configLoaded={configLoaded}
            onChange={saveSettings}
            onResumeUpload={handleResumeUpload}
            defaultTemplate={DEFAULT_TEMPLATE}
          />
        </aside>

        <main style={styles.main}>
          <div style={styles.tabs}>
            <button
              style={{ ...styles.tab, ...(activeTab === 'upload' ? styles.tabActive : {}) }}
              onClick={() => setActiveTab('upload')}
            >
              Upload Screenshots
            </button>
            <button
              style={{ ...styles.tab, ...(activeTab === 'find' ? styles.tabActive : {}) }}
              onClick={() => setActiveTab('find')}
            >
              Find on LinkedIn
            </button>
            <button
              style={{ ...styles.tab, ...(activeTab === 'tracker' ? styles.tabActive : {}) }}
              onClick={() => setActiveTab('tracker')}
            >
              Tracker & Analytics
            </button>
          </div>

          {activeTab === 'upload' && (
            <ScreenshotUpload onUpload={handleUpload} disabled={loading} />
          )}
          {/* Keep FindJobs mounted so search results survive tab switches */}
          <div style={{ display: activeTab === 'find' ? 'block' : 'none' }}>
            <FindJobs onImported={handleImportPosts} disabled={loading} settings={settings} />
          </div>
          {activeTab === 'tracker' && (
            <TrackerPanel onJobsChanged={refreshJobs} />
          )}

          {activeTab !== 'tracker' && (
            <>
          <div style={styles.actionBar}>
            <button
              className="btn-primary"
              onClick={handleProcessAll}
              disabled={loading || selectedIds.size === 0}
            >
              {loading ? 'Processing...' : `Extract & Generate (${selectedIds.size} selected)`}
            </button>
            <button
              className="btn-secondary"
              onClick={openPreview}
              disabled={loading || !jobs.some((j) =>
                (j.status === 'email_generated' || j.status === 'failed')
                && (j.email?.to_email || j.email_ai?.to_email),
              )}
            >
              Review & Send Emails
            </button>
          </div>

          <JobList
            jobs={jobs}
            selectedIds={selectedIds}
            onToggleSelect={toggleSelect}
            onSelectAll={selectAll}
            onDelete={handleDelete}
            onPreview={openPreview}
            onFixEmail={handleFixEmail}
          />
            </>
          )}
        </main>
      </div>

      {previewOpen && (
        <EmailPreviewModal
          key={previewJobId || 'all'}
          jobs={jobs}
          initialJobId={previewJobId}
          resumeDisplayName={settings.resumeDisplayName}
          onClose={() => { setPreviewOpen(false); setPreviewJobId(null) }}
          onSend={handleApproveAndSend}
          sending={sending}
          onJobUpdated={(updated) => {
            setJobs((prev) => prev.map((j) => (j.id === updated.id ? { ...j, ...updated } : j)))
          }}
        />
      )}
    </div>
  )
}

const styles = {
  app: { minHeight: '100vh', padding: '24px 32px' },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 32,
    paddingBottom: 24,
    borderBottom: '1px solid var(--border)',
  },
  title: { fontSize: 28, fontWeight: 700, letterSpacing: '-0.02em' },
  subtitle: { color: 'var(--text-muted)', marginTop: 6, fontSize: 15 },
  headerActions: { display: 'flex', gap: 12, alignItems: 'center' },
  apiBadge: { padding: '6px 12px', borderRadius: 20, fontSize: 12, fontWeight: 600 },
  toast: {
    position: 'fixed',
    top: 24,
    right: 24,
    padding: '14px 20px',
    borderRadius: 10,
    fontWeight: 500,
    zIndex: 1000,
    boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
  },
  layout: { display: 'grid', gridTemplateColumns: '340px 1fr', gap: 28 },
  sidebar: {
    background: 'var(--surface)',
    borderRadius: 'var(--radius)',
    padding: 24,
    border: '1px solid var(--border)',
    height: 'fit-content',
    position: 'sticky',
    top: 24,
  },
  main: { display: 'flex', flexDirection: 'column', gap: 24, minWidth: 0, overflow: 'hidden' },
  actionBar: { display: 'flex', gap: 12, flexWrap: 'wrap' },
  tabs: { display: 'flex', gap: 8, marginBottom: -8 },
  tab: {
    padding: '10px 18px', borderRadius: 'var(--radius) var(--radius) 0 0',
    border: '1px solid var(--border)', borderBottom: 'none',
    background: 'var(--bg)', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 14,
  },
  tabActive: {
    background: 'var(--surface)', color: 'var(--text)', fontWeight: 600,
    borderColor: 'var(--border)',
  },
}
