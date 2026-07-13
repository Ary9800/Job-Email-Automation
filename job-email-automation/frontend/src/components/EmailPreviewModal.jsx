import { useEffect, useState } from 'react'

export default function EmailPreviewModal({
  jobs,
  resumeDisplayName,
  onClose,
  onSend,
  sending,
  initialJobId,
}) {
  const pendingJobs = jobs.filter(
    (j) => j.status === 'email_generated' && j.email?.to_email,
  )

  const [currentIndex, setCurrentIndex] = useState(0)
  const [drafts, setDrafts] = useState(() => buildInitialDrafts(jobs))
  const [emailMode, setEmailMode] = useState(() => buildInitialModes(jobs))
  const [skipped, setSkipped] = useState(new Set())
  const [sent, setSent] = useState(new Set())

  useEffect(() => {
    if (initialJobId) {
      const idx = pendingJobs.findIndex((j) => j.id === initialJobId)
      if (idx >= 0) setCurrentIndex(idx)
    }
  }, [initialJobId])

  const reviewable = pendingJobs.filter((j) => !skipped.has(j.id) && !sent.has(j.id))
  const currentJob = reviewable[currentIndex] || null
  const currentDraft = currentJob ? drafts[currentJob.id] : null
  const currentMode = currentJob ? (emailMode[currentJob.id] || 'ai') : 'ai'

  const updateDraft = (field, value) => {
    if (!currentJob) return
    setDrafts((prev) => ({
      ...prev,
      [currentJob.id]: { ...prev[currentJob.id], [field]: value },
    }))
  }

  const switchMode = (mode) => {
    if (!currentJob) return
    const source = mode === 'ai' ? currentJob.email_ai : currentJob.email_static
    if (!source) return

    setEmailMode((prev) => ({ ...prev, [currentJob.id]: mode }))
    setDrafts((prev) => ({
      ...prev,
      [currentJob.id]: {
        ...prev[currentJob.id],
        subject: source.subject,
        body: source.body,
        mode,
      },
    }))
  }

  const handleApproveAndSend = async () => {
    if (!currentJob || !currentDraft) return
    await onSend(currentJob.id, currentDraft)
    setSent((prev) => new Set([...prev, currentJob.id]))
    if (currentIndex >= reviewable.length - 1) {
      setCurrentIndex(Math.max(0, currentIndex - 1))
    }
  }

  const handleSkip = () => {
    if (!currentJob) return
    setSkipped((prev) => new Set([...prev, currentJob.id]))
    if (currentIndex >= reviewable.length - 1) {
      setCurrentIndex(Math.max(0, currentIndex - 1))
    }
  }

  const allDone = pendingJobs.every((j) => sent.has(j.id) || skipped.has(j.id))

  if (pendingJobs.length === 0) {
    return (
      <ModalOverlay onClose={onClose}>
        <div style={styles.modal}>
          <h2 style={styles.title}>No emails to preview</h2>
          <p style={styles.subtitle}>Generate emails first using "Extract & Generate".</p>
          <button className="btn-secondary" onClick={onClose}>Close</button>
        </div>
      </ModalOverlay>
    )
  }

  return (
    <ModalOverlay onClose={onClose}>
      <div style={styles.modal}>
        <div style={styles.modalHeader}>
          <div>
            <h2 style={styles.title}>Review before sending</h2>
            <p style={styles.subtitle}>
              AI writes a tailored email per job. Switch to Static if you prefer your template.
            </p>
          </div>
          <button className="btn-secondary" onClick={onClose} style={styles.closeBtn}>✕</button>
        </div>

        <div style={styles.progress}>
          <span style={styles.progressText}>
            {sent.size} sent · {skipped.size} skipped · {reviewable.length} remaining
          </span>
          <div style={styles.progressBar}>
            <div style={{
              ...styles.progressFill,
              width: `${((sent.size + skipped.size) / pendingJobs.length) * 100}%`,
            }} />
          </div>
        </div>

        <div style={styles.body}>
          <aside style={styles.sidebar}>
            <h3 style={styles.sidebarTitle}>Emails ({pendingJobs.length})</h3>
            {pendingJobs.map((job) => {
              const isSent = sent.has(job.id)
              const isSkipped = skipped.has(job.id)
              const isActive = currentJob?.id === job.id
              const reviewIdx = reviewable.findIndex((j) => j.id === job.id)

              return (
                <button
                  key={job.id}
                  style={{
                    ...styles.sidebarItem,
                    background: isActive ? 'var(--accent)' : isSent ? '#14532d33' : isSkipped ? '#374151' : 'var(--bg)',
                    borderColor: isActive ? 'var(--accent)' : 'var(--border)',
                    opacity: isSkipped ? 0.6 : 1,
                  }}
                  onClick={() => !isSent && !isSkipped && setCurrentIndex(reviewIdx >= 0 ? reviewIdx : 0)}
                  disabled={isSent || isSkipped}
                >
                  <span style={styles.sidebarItemTitle}>{job.extracted?.role || job.filename}</span>
                  <span style={styles.sidebarItemMeta}>{job.extracted?.company || '—'}</span>
                  {isSent && <span style={styles.badgeSent}>✓ Sent</span>}
                  {isSkipped && <span style={styles.badgeSkipped}>Skipped</span>}
                </button>
              )
            })}
          </aside>

          {currentJob && currentDraft ? (
            <main style={styles.preview}>
              <div style={styles.jobContext}>
                <ContextTag label="Role" value={currentJob.extracted?.role} />
                <ContextTag label="Company" value={currentJob.extracted?.company} />
                <ContextTag label="Platform" value={currentJob.extracted?.source_platform} />
              </div>

              {currentJob.extracted?.content_summary && (
                <div style={styles.aiInsight}>
                  <strong>AI understood this post as:</strong> {currentJob.extracted.content_summary}
                </div>
              )}

              {currentJob.extracted?.skills_required?.length > 0 && (
                <div style={styles.skillsRow}>
                  {currentJob.extracted.skills_required.slice(0, 8).map((s) => (
                    <span key={s} style={styles.skillChip}>{s}</span>
                  ))}
                </div>
              )}

              {/* AI vs Static toggle */}
              <div style={styles.modeToggle}>
                <span style={styles.modeLabel}>Email version:</span>
                <button
                  style={{
                    ...styles.modeBtn,
                    background: currentMode === 'ai' ? 'var(--accent)' : 'var(--bg)',
                    color: currentMode === 'ai' ? 'white' : 'var(--text-muted)',
                  }}
                  onClick={() => switchMode('ai')}
                >
                  ✨ AI Generated
                </button>
                <button
                  style={{
                    ...styles.modeBtn,
                    background: currentMode === 'static' ? '#374151' : 'var(--bg)',
                    color: currentMode === 'static' ? 'white' : 'var(--text-muted)',
                    borderColor: currentMode === 'static' ? '#6b7280' : 'var(--border)',
                  }}
                  onClick={() => switchMode('static')}
                  disabled={!currentJob.email_static}
                >
                  📋 Static Template
                </button>
                <span style={styles.modeHint}>
                  {currentMode === 'ai'
                    ? 'Tailored to this job post by Ollama'
                    : 'Your fixed Java template'}
                </span>
              </div>

              <div style={styles.emailMeta}>
                <div className="form-group">
                  <label>To</label>
                  <input
                    value={currentDraft.to_email}
                    onChange={(e) => updateDraft('to_email', e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label>Subject</label>
                  <input
                    value={currentDraft.subject}
                    onChange={(e) => updateDraft('subject', e.target.value)}
                  />
                </div>
              </div>

              <div className="form-group" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <label>Email body {currentMode === 'ai' ? '(AI — edit if needed)' : '(Static — edit if needed)'}</label>
                <textarea
                  value={currentDraft.body}
                  onChange={(e) => updateDraft('body', e.target.value)}
                  style={styles.bodyTextarea}
                />
              </div>

              {resumeDisplayName && (
                <div style={styles.attachment}>
                  📎 Resume attached: <strong>{resumeDisplayName}</strong>
                </div>
              )}

              <div style={styles.actions}>
                <div style={styles.navButtons}>
                  <button className="btn-secondary" disabled={currentIndex === 0 || sending} onClick={() => setCurrentIndex((i) => i - 1)}>
                    ← Previous
                  </button>
                  <button className="btn-secondary" disabled={currentIndex >= reviewable.length - 1 || sending} onClick={() => setCurrentIndex((i) => i + 1)}>
                    Next →
                  </button>
                </div>
                <div style={styles.sendButtons}>
                  <button className="btn-secondary" onClick={handleSkip} disabled={sending}>Skip</button>
                  <button
                    className="btn-primary"
                    onClick={handleApproveAndSend}
                    disabled={sending || !currentDraft.to_email || !currentDraft.subject}
                    style={{ background: '#16a34a', minWidth: 160 }}
                  >
                    {sending ? 'Sending...' : `Approve & Send (${currentMode === 'ai' ? 'AI' : 'Static'})`}
                  </button>
                </div>
              </div>
            </main>
          ) : (
            <main style={styles.preview}>
              <div style={styles.allDone}>
                <div style={styles.allDoneIcon}>✓</div>
                <h3>All emails reviewed</h3>
                <p>{sent.size} sent, {skipped.size} skipped</p>
                <button className="btn-primary" onClick={onClose}>Close</button>
              </div>
            </main>
          )}
        </div>
      </div>
    </ModalOverlay>
  )
}

function buildInitialDrafts(jobs) {
  const initial = {}
  jobs
    .filter((j) => j.status === 'email_generated' && j.email?.to_email)
    .forEach((job) => {
      const email = job.email_ai || job.email
      initial[job.id] = {
        to_email: email.to_email,
        to_name: email.to_name || '',
        subject: email.subject,
        body: email.body,
        mode: 'ai',
      }
    })
  return initial
}

function buildInitialModes(jobs) {
  const modes = {}
  jobs
    .filter((j) => j.status === 'email_generated')
    .forEach((job) => { modes[job.id] = 'ai' })
  return modes
}

function ModalOverlay({ children, onClose }) {
  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.overlayInner} onClick={(e) => e.stopPropagation()}>{children}</div>
    </div>
  )
}

function ContextTag({ label, value }) {
  if (!value) return null
  return (
    <span style={styles.contextTag}>
      <span style={styles.contextLabel}>{label}:</span> {value}
    </span>
  )
}

const styles = {
  overlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', zIndex: 2000,
    display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24,
  },
  overlayInner: { width: '100%', maxWidth: 1100 },
  modal: {
    background: 'var(--surface)', borderRadius: 'var(--radius)', border: '1px solid var(--border)',
    maxHeight: '90vh', display: 'flex', flexDirection: 'column', overflow: 'hidden',
  },
  modalHeader: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
    padding: '20px 24px', borderBottom: '1px solid var(--border)',
  },
  title: { fontSize: 20, fontWeight: 700 },
  subtitle: { fontSize: 13, color: 'var(--text-muted)', marginTop: 4 },
  closeBtn: { padding: '8px 12px', fontSize: 16 },
  progress: { padding: '12px 24px', borderBottom: '1px solid var(--border)' },
  progressText: { fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 8 },
  progressBar: { height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' },
  progressFill: { height: '100%', background: 'var(--success)', transition: 'width 0.3s ease' },
  body: { display: 'grid', gridTemplateColumns: '240px 1fr', flex: 1, overflow: 'hidden', minHeight: 0 },
  sidebar: {
    borderRight: '1px solid var(--border)', padding: 16, overflowY: 'auto',
    display: 'flex', flexDirection: 'column', gap: 8,
  },
  sidebarTitle: { fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase' },
  sidebarItem: {
    textAlign: 'left', padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)',
    cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 2,
  },
  sidebarItemTitle: { fontSize: 13, fontWeight: 600, color: 'var(--text)' },
  sidebarItemMeta: { fontSize: 11, color: 'var(--text-muted)' },
  badgeSent: { fontSize: 10, color: 'var(--success)', fontWeight: 600, marginTop: 4 },
  badgeSkipped: { fontSize: 10, color: 'var(--text-muted)', fontWeight: 600, marginTop: 4 },
  preview: { padding: 24, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 16 },
  jobContext: { display: 'flex', flexWrap: 'wrap', gap: 8 },
  contextTag: { fontSize: 12, padding: '4px 10px', background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border)' },
  contextLabel: { fontWeight: 600, color: 'var(--text-muted)' },
  aiInsight: {
    fontSize: 13, padding: '10px 14px', background: 'rgba(59,130,246,0.08)',
    borderRadius: 8, border: '1px solid rgba(59,130,246,0.2)', lineHeight: 1.5,
  },
  skillsRow: { display: 'flex', flexWrap: 'wrap', gap: 6 },
  skillChip: {
    fontSize: 11, padding: '3px 8px', background: 'var(--bg)', borderRadius: 6,
    border: '1px solid var(--border)', color: 'var(--text-muted)',
  },
  modeToggle: {
    display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
    padding: '12px 14px', background: 'var(--bg)', borderRadius: 8, border: '1px solid var(--border)',
  },
  modeLabel: { fontSize: 13, fontWeight: 600, color: 'var(--text-muted)' },
  modeBtn: {
    padding: '8px 14px', borderRadius: 6, border: '1px solid var(--border)',
    fontSize: 13, fontWeight: 500, cursor: 'pointer',
  },
  modeHint: { fontSize: 12, color: 'var(--text-muted)', marginLeft: 4 },
  emailMeta: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 },
  bodyTextarea: { flex: 1, minHeight: 220, resize: 'vertical', fontFamily: 'inherit', lineHeight: 1.6 },
  attachment: {
    fontSize: 13, padding: '10px 14px', background: 'var(--bg)',
    borderRadius: 8, border: '1px solid var(--border)', color: 'var(--text-muted)',
  },
  actions: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    paddingTop: 16, borderTop: '1px solid var(--border)', flexWrap: 'wrap', gap: 12,
  },
  navButtons: { display: 'flex', gap: 8 },
  sendButtons: { display: 'flex', gap: 8 },
  allDone: {
    textAlign: 'center', padding: 48, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12,
  },
  allDoneIcon: {
    width: 56, height: 56, borderRadius: '50%', background: '#14532d', color: '#4ade80',
    fontSize: 28, display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
}
