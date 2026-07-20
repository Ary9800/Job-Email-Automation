import { useState } from 'react'

export default function JobList({
  jobs,
  selectedIds,
  onToggleSelect,
  onSelectAll,
  onDelete,
  onPreview,
  onFixEmail,
}) {
  const [expanded, setExpanded] = useState(null)
  const [manualEmails, setManualEmails] = useState({})
  const [fixing, setFixing] = useState(null)

  const selectableJobs = jobs.filter((j) => j.status !== 'sent')
  const allSelected = selectableJobs.length > 0 && selectableJobs.every((j) => selectedIds.has(j.id))

  const handleSelectAll = () => {
    if (allSelected) {
      onSelectAll([])
    } else {
      onSelectAll(selectableJobs.map((j) => j.id))
    }
  }

  if (jobs.length === 0) {
    return (
      <div style={styles.empty}>
        <p>No screenshots uploaded yet</p>
        <p style={styles.emptyHint}>Upload job post screenshots to get started</p>
      </div>
    )
  }

  return (
    <div style={styles.list}>
      <div style={styles.listHeader}>
        <h2 style={styles.heading}>Jobs ({jobs.length})</h2>
        <label style={styles.selectAll} className="inline-label">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={handleSelectAll}
            disabled={selectableJobs.length === 0}
          />
          Select all ({selectableJobs.length})
        </label>
      </div>

      {jobs.map((job) => {
        const isSent = job.status === 'sent'
        const isSelected = selectedIds.has(job.id)

        return (
          <div
            key={job.id}
            style={{
              ...styles.card,
              opacity: isSent ? 0.65 : 1,
              borderColor: isSelected ? 'var(--accent)' : 'var(--border)',
            }}
          >
            <div style={styles.cardHeader}>
              <div style={styles.cardTitle} className="inline-check">
                <input
                  type="checkbox"
                  checked={isSelected}
                  disabled={isSent}
                  onChange={() => onToggleSelect(job.id)}
                  title={isSent ? 'Already sent' : 'Select to process'}
                />
                <span style={styles.filename}>{job.filename}</span>
                {job.has_screenshot && (
                  <img
                    src={`/api/jobs/${job.id}/screenshot`}
                    alt=""
                    style={styles.thumb}
                    onError={(e) => { e.currentTarget.style.display = 'none' }}
                  />
                )}
                {job.source_url && (
                  <a
                    href={job.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={styles.sourceLink}
                    title="Open LinkedIn post"
                  >
                    ↗
                  </a>
                )}
                <span className={`status-badge status-${job.status}`}>
                  {job.status.replace('_', ' ')}
                </span>
              </div>
              <div style={styles.cardActions}>
                {job.status === 'email_generated' && job.email?.to_email && (
                  <button
                    className="btn-primary"
                    style={{ padding: '6px 12px', fontSize: 12, background: '#16a34a' }}
                    onClick={() => onPreview(job.id)}
                  >
                    Preview & Send
                  </button>
                )}
                {job.status === 'failed' && (job.email?.to_email || job.email_ai?.to_email) && (
                  <button
                    className="btn-primary"
                    style={{ padding: '6px 12px', fontSize: 12, background: '#ea580c' }}
                    onClick={() => onPreview(job.id)}
                  >
                    Retry Send
                  </button>
                )}
                {job.status === 'sent' && (job.email?.to_email || job.email_ai?.to_email) && (
                  <button
                    className="btn-primary"
                    style={{ padding: '6px 12px', fontSize: 12, background: '#2563eb' }}
                    onClick={() => onPreview(job.id)}
                  >
                    Edit & Resend
                  </button>
                )}
                <button
                  className="btn-secondary"
                  style={{ padding: '6px 12px', fontSize: 12 }}
                  onClick={() => setExpanded(expanded === job.id ? null : job.id)}
                >
                  {expanded === job.id ? 'Collapse' : 'Details'}
                </button>
                <button
                  className="btn-danger"
                  style={{ padding: '6px 12px', fontSize: 12 }}
                  onClick={() => onDelete(job.id)}
                >
                  Remove
                </button>
              </div>
            </div>

            {isSent && (
              <p style={styles.sentNote}>
                ✓ Email already sent
                {job.outcome && job.outcome !== 'none' ? ` · ${job.outcome.replace('_', ' ')}` : ' · waiting'}
                {job.sent_at ? ` · ${job.sent_at}` : ''}
                {' — use Edit & Resend to fix and send again'}
              </p>
            )}

            {job.extracted && (
              <div style={styles.summary}>
                <Tag label="Role" value={job.extracted.role} />
                <Tag label="Company" value={job.extracted.company} />
                <Tag label="Email" value={job.extracted.recruiter_email} highlight />
                <Tag label="Recruiter" value={job.extracted.recruiter_name} />
              </div>
            )}

            {job.error && !isSent && (
              <div style={styles.errorBox}>
                <p style={styles.error}>⚠ {job.error}</p>
                {job.extracted?.raw_text && (
                  <details style={styles.rawDetails}>
                    <summary>OCR read this from image</summary>
                    <pre style={styles.rawText}>{job.extracted.raw_text}</pre>
                  </details>
                )}
                <div style={styles.manualFix}>
                  <input
                    type="email"
                    placeholder="e.g. piyusha.r@apideltech.com"
                    value={manualEmails[job.id] || ''}
                    onChange={(e) => setManualEmails((prev) => ({ ...prev, [job.id]: e.target.value }))}
                    style={styles.manualInput}
                  />
                  <button
                    className="btn-primary"
                    style={{ padding: '8px 14px', fontSize: 12 }}
                    disabled={fixing === job.id || !manualEmails[job.id]}
                    onClick={async () => {
                      setFixing(job.id)
                      try {
                        await onFixEmail(job.id, { recruiter_email: manualEmails[job.id] })
                      } finally {
                        setFixing(null)
                      }
                    }}
                  >
                    {fixing === job.id ? 'Saving...' : 'Add Email & Continue'}
                  </button>
                </div>
              </div>
            )}

            {expanded === job.id && (
              <div style={styles.details}>
                {job.email && (
                  <section>
                    <h4>Generated Email</h4>
                    <p><strong>Subject:</strong> {job.email.subject}</p>
                    <pre style={styles.emailBody}>{job.email.body}</pre>
                  </section>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function Tag({ label, value, highlight }) {
  if (!value) return null
  return (
    <span style={{
      ...styles.tag,
      borderColor: highlight ? 'var(--accent)' : 'var(--border)',
      color: highlight ? 'var(--accent)' : 'var(--text-muted)',
    }}>
      <span style={styles.tagLabel}>{label}:</span> {value}
    </span>
  )
}

const styles = {
  list: { display: 'flex', flexDirection: 'column', gap: 12 },
  listHeader: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4,
  },
  heading: { fontSize: 18, fontWeight: 600 },
  selectAll: {
    display: 'flex', alignItems: 'center', gap: 8, fontSize: 13,
    color: 'var(--text-muted)', cursor: 'pointer',
  },
  empty: {
    textAlign: 'center', padding: 48, background: 'var(--surface)',
    borderRadius: 'var(--radius)', border: '1px solid var(--border)', color: 'var(--text-muted)',
  },
  emptyHint: { fontSize: 13, marginTop: 8 },
  card: {
    background: 'var(--surface)', borderRadius: 'var(--radius)',
    border: '1px solid var(--border)', padding: 16,
  },
  cardHeader: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8,
  },
  cardTitle: { display: 'flex', alignItems: 'center', gap: 10 },
  filename: { fontWeight: 500 },
  thumb: {
    width: 40, height: 40, objectFit: 'cover', borderRadius: 6,
    border: '1px solid var(--border)',
  },
  sourceLink: { fontSize: 14, color: 'var(--accent)', textDecoration: 'none' },
  cardActions: { display: 'flex', gap: 8 },
  sentNote: { fontSize: 12, color: 'var(--success)', marginTop: 8 },
  summary: { display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 },
  tag: {
    fontSize: 13, padding: '4px 10px', borderRadius: 6,
    border: '1px solid var(--border)', background: 'var(--bg)',
  },
  tagLabel: { fontWeight: 600, marginRight: 4 },
  error: { color: 'var(--error)', fontSize: 13 },
  errorBox: {
    marginTop: 12, padding: 12, background: 'rgba(239,68,68,0.08)',
    borderRadius: 8, border: '1px solid rgba(239,68,68,0.2)',
  },
  manualFix: { display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 },
  manualInput: { flex: 1, minWidth: 200 },
  rawDetails: { fontSize: 12, marginTop: 8, color: 'var(--text-muted)' },
  rawText: {
    fontSize: 11, background: 'var(--bg)', padding: 8, borderRadius: 6,
    marginTop: 6, whiteSpace: 'pre-wrap', maxHeight: 120, overflow: 'auto',
  },
  details: {
    marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)',
  },
  emailBody: {
    background: 'var(--bg)', padding: 12, borderRadius: 8, fontSize: 13,
    whiteSpace: 'pre-wrap', marginTop: 8, border: '1px solid var(--border)',
  },
}
