import { useEffect, useState } from 'react'
import {
  fetchAnalytics,
  updateJobOutcome,
  fetchScheduler,
  updateScheduler,
  runSchedulerNow,
  fetchResumeProfiles,
  saveResumeProfiles,
  fetchRoleTemplates,
} from '../api'

const OUTCOMES = [
  { value: 'waiting', label: 'Waiting' },
  { value: 'replied', label: 'Replied' },
  { value: 'interview', label: 'Interview' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'hired', label: 'Hired' },
  { value: 'no_response', label: 'No response' },
]

export default function TrackerPanel({ onJobsChanged }) {
  const [analytics, setAnalytics] = useState(null)
  const [scheduler, setScheduler] = useState(null)
  const [profiles, setProfiles] = useState([])
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState(null)
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [a, s, r, t] = await Promise.all([
        fetchAnalytics(),
        fetchScheduler(),
        fetchResumeProfiles(),
        fetchRoleTemplates(),
      ])
      setAnalytics(a)
      setScheduler(s)
      setProfiles(r.profiles || [])
      setTemplates(t.templates || [])
    } catch (e) {
      setMessage({ type: 'error', text: e.message })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const setOutcome = async (jobId, outcome) => {
    try {
      await updateJobOutcome(jobId, outcome)
      await load()
      onJobsChanged?.()
    } catch (e) {
      setMessage({ type: 'error', text: e.message })
    }
  }

  const saveSched = async () => {
    setSaving(true)
    try {
      const updated = await updateScheduler(scheduler)
      setScheduler(updated)
      setMessage({ type: 'ok', text: 'Scheduler saved' })
    } catch (e) {
      setMessage({ type: 'error', text: e.message })
    } finally {
      setSaving(false)
    }
  }

  const runNow = async () => {
    setSaving(true)
    setMessage(null)
    try {
      const result = await runSchedulerNow()
      setMessage({
        type: 'ok',
        text: `Run done — found ${result.found}, imported ${result.imported}, generated ${result.generated}`,
      })
      await load()
      onJobsChanged?.()
    } catch (e) {
      setMessage({ type: 'error', text: e.message })
    } finally {
      setSaving(false)
    }
  }

  const saveProfiles = async () => {
    setSaving(true)
    try {
      await saveResumeProfiles(profiles)
      setMessage({ type: 'ok', text: 'Resume profiles saved' })
    } catch (e) {
      setMessage({ type: 'error', text: e.message })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div style={styles.box}>Loading tracker…</div>
  }

  const summary = analytics?.summary || {}

  return (
    <div style={styles.wrap}>
      {message && (
        <div style={{
          ...styles.msg,
          color: message.type === 'error' ? '#f87171' : '#4ade80',
        }}>
          {message.text}
        </div>
      )}

      <section style={styles.box}>
        <h2 style={styles.h2}>Analytics</h2>
        <div style={styles.stats}>
          <Stat label="Total jobs" value={summary.total_jobs || 0} />
          <Stat label="Sent" value={summary.sent || 0} />
          <Stat label="Replied" value={summary.replied || 0} />
          <Stat label="Interview" value={summary.interview || 0} />
          <Stat label="Reply rate" value={`${summary.reply_rate_pct || 0}%`} />
        </div>

        <h3 style={styles.h3}>By role</h3>
        <div style={styles.table}>
          {Object.entries(analytics?.by_role || {}).map(([role, row]) => (
            <div key={role} style={styles.row}>
              <span style={styles.role}>{role}</span>
              <span style={styles.muted}>
                {row.sent} sent · {row.replied} replied · {row.interview} interview
              </span>
            </div>
          ))}
          {Object.keys(analytics?.by_role || {}).length === 0 && (
            <p style={styles.muted}>No data yet — send some applications first.</p>
          )}
        </div>
      </section>

      <section style={styles.box}>
        <h2 style={styles.h2}>Application tracker</h2>
        <p style={styles.muted}>Update outcomes after recruiters reply.</p>
        <div style={styles.trackerList}>
          {(analytics?.tracked_jobs || []).map((job) => (
            <div key={job.id} style={styles.trackCard}>
              <div>
                <strong>{job.extracted?.role || job.filename}</strong>
                <div style={styles.muted}>
                  {job.extracted?.company || '—'} · {job.extracted?.recruiter_email || '—'}
                </div>
                {job.sent_at && <div style={styles.muted}>Sent {job.sent_at}</div>}
              </div>
              <select
                value={job.outcome || 'waiting'}
                onChange={(e) => setOutcome(job.id, e.target.value)}
                style={styles.select}
              >
                {OUTCOMES.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
          ))}
          {(analytics?.tracked_jobs || []).length === 0 && (
            <p style={styles.muted}>No sent applications yet.</p>
          )}
        </div>
      </section>

      <section style={styles.box}>
        <h2 style={styles.h2}>Daily auto-run</h2>
        <p style={styles.muted}>
          Runs on the server clock. Searches LinkedIn posts, imports new ones, generates drafts.
        </p>
        {scheduler && (
          <div style={styles.form}>
            <label className="inline-label">
              <input
                type="checkbox"
                checked={!!scheduler.enabled}
                onChange={(e) => setScheduler({ ...scheduler, enabled: e.target.checked })}
              />
              Enable daily run
            </label>
            <div style={styles.row2}>
              <div>
                <label>Hour (0–23)</label>
                <input
                  type="number"
                  min={0}
                  max={23}
                  value={scheduler.hour ?? 9}
                  onChange={(e) => setScheduler({ ...scheduler, hour: Number(e.target.value) })}
                />
              </div>
              <div>
                <label>Minute</label>
                <input
                  type="number"
                  min={0}
                  max={59}
                  value={scheduler.minute ?? 0}
                  onChange={(e) => setScheduler({ ...scheduler, minute: Number(e.target.value) })}
                />
              </div>
              <div>
                <label>Posted</label>
                <select
                  value={scheduler.time_period || 'day'}
                  onChange={(e) => setScheduler({ ...scheduler, time_period: e.target.value })}
                >
                  <option value="day">Past 1 day</option>
                  <option value="week">Past 1 week</option>
                  <option value="month">Past 1 month</option>
                </select>
              </div>
              <div>
                <label>Experience</label>
                <select
                  value={scheduler.experience_range || '2-4'}
                  onChange={(e) => setScheduler({ ...scheduler, experience_range: e.target.value })}
                >
                  <option value="any">Any</option>
                  <option value="2+">2+</option>
                  <option value="2-3">2–3</option>
                  <option value="2-4">2–4</option>
                  <option value="3+">3+</option>
                  <option value="3-5">3–5</option>
                </select>
              </div>
            </div>
            {scheduler.last_run_at && (
              <p style={styles.muted}>
                Last run: {scheduler.last_run_at}
                {scheduler.last_run_summary
                  ? ` · imported ${scheduler.last_run_summary.imported}, generated ${scheduler.last_run_summary.generated}`
                  : ''}
              </p>
            )}
            <div style={styles.actions}>
              <button className="btn-primary" onClick={saveSched} disabled={saving}>Save schedule</button>
              <button className="btn-secondary" onClick={runNow} disabled={saving}>Run now</button>
            </div>
          </div>
        )}
      </section>

      <section style={styles.box}>
        <h2 style={styles.h2}>Multi-resume (by role)</h2>
        <p style={styles.muted}>
          Upload resumes in Settings, then map filenames here. Keywords pick the resume for each job role.
        </p>
        {profiles.map((p, idx) => (
          <div key={p.id || idx} style={styles.profileCard}>
            <input
              value={p.label || ''}
              onChange={(e) => {
                const next = [...profiles]
                next[idx] = { ...p, label: e.target.value }
                setProfiles(next)
              }}
              placeholder="Label"
            />
            <input
              value={p.filename || ''}
              onChange={(e) => {
                const next = [...profiles]
                next[idx] = { ...p, filename: e.target.value || null }
                setProfiles(next)
              }}
              placeholder="Resume filename in backend/resumes/ (e.g. resume_xxxx.pdf)"
            />
            <input
              value={(p.role_keywords || []).join(', ')}
              onChange={(e) => {
                const next = [...profiles]
                next[idx] = {
                  ...p,
                  role_keywords: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                }
                setProfiles(next)
              }}
              placeholder="Keywords: backend, java backend, spring"
            />
          </div>
        ))}
        <button className="btn-secondary" onClick={saveProfiles} disabled={saving}>
          Save resume profiles
        </button>
      </section>

      <section style={styles.box}>
        <h2 style={styles.h2}>Role email templates</h2>
        <p style={styles.muted}>
          Stored in <code>backend/data/role_templates.json</code>. Matching keywords override the default static template when generating.
        </p>
        <ul style={styles.list}>
          {templates.map((t) => (
            <li key={t.id}>
              <strong>{t.label}</strong>
              <span style={styles.muted}>
                {' '}— keywords: {(t.role_keywords || []).join(', ') || '(default)'}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div style={styles.stat}>
      <div style={styles.statValue}>{value}</div>
      <div style={styles.statLabel}>{label}</div>
    </div>
  )
}

const styles = {
  wrap: { display: 'flex', flexDirection: 'column', gap: 16 },
  box: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding: 20,
  },
  h2: { fontSize: 18, fontWeight: 600, marginBottom: 8 },
  h3: { fontSize: 14, fontWeight: 600, margin: '16px 0 8px' },
  muted: { fontSize: 12, color: 'var(--text-muted)' },
  stats: { display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 12 },
  stat: {
    minWidth: 90, padding: '10px 14px', borderRadius: 8,
    background: 'var(--bg)', border: '1px solid var(--border)',
  },
  statValue: { fontSize: 22, fontWeight: 700 },
  statLabel: { fontSize: 11, color: 'var(--text-muted)' },
  table: { display: 'flex', flexDirection: 'column', gap: 6 },
  row: { display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 },
  role: { fontWeight: 500 },
  trackerList: { display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12 },
  trackCard: {
    display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center',
    padding: 12, borderRadius: 8, background: 'var(--bg)', border: '1px solid var(--border)',
  },
  select: { width: 'auto', minWidth: 140 },
  form: { display: 'flex', flexDirection: 'column', gap: 12, marginTop: 12 },
  row2: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 12 },
  actions: { display: 'flex', gap: 10 },
  profileCard: { display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12 },
  list: { marginTop: 8, paddingLeft: 18, fontSize: 13 },
  msg: { padding: 10, borderRadius: 8, background: 'var(--surface)', fontSize: 13 },
}
