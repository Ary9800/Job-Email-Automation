import { useState } from 'react'
import { findLinkedInJobs, importLinkedInPosts, pasteLinkedInPost, enrichLinkedInPost } from '../api'

const DEFAULT_ROLES = [
  'Java Backend Engineer',
  'Java Backend Developer',
  'Java Full Stack Developer',
  'Java Software Engineer',
  'Java Developer',
  'Software Engineer',
  'Backend Engineer',
]

const TIME_PERIODS = [
  { value: 'day', label: 'Past 1 day' },
  { value: 'week', label: 'Past 1 week' },
  { value: 'month', label: 'Past 1 month' },
]

const EXPERIENCE_OPTIONS = [
  { value: 'any', label: 'Any experience' },
  { value: '2+', label: '2+ years' },
  { value: '2-3', label: '2–3 years' },
  { value: '2-4', label: '2–4 years' },
  { value: '3+', label: '3+ years' },
  { value: '3-5', label: '3–5 years' },
]

function truncate(text, max = 120) {
  if (!text) return ''
  return text.length > max ? `${text.slice(0, max)}…` : text
}

export default function FindJobs({ onImported, disabled, settings }) {
  const [roles, setRoles] = useState(new Set(DEFAULT_ROLES))
  const [timePeriod, setTimePeriod] = useState('week')
  const [experienceRange, setExperienceRange] = useState('2-4')
  const [posts, setPosts] = useState([])
  const [selected, setSelected] = useState(new Set())
  const [searching, setSearching] = useState(false)
  const [importing, setImporting] = useState(false)
  const [pasting, setPasting] = useState(false)
  const [enrichingId, setEnrichingId] = useState(null)
  const [searched, setSearched] = useState(false)
  const [searchProvider, setSearchProvider] = useState(null)
  const [error, setError] = useState(null)
  const [pasteUrl, setPasteUrl] = useState('')
  const [pasteText, setPasteText] = useState('')

  const generateOptions = () => ({
    autoGenerate: true,
    sender: settings?.sender,
    template: settings?.template,
    candidate: settings?.candidate,
  })

  const toggleRole = (role) => {
    setRoles((prev) => {
      const next = new Set(prev)
      if (next.has(role)) next.delete(role)
      else next.add(role)
      return next
    })
  }

  const togglePost = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const selectAll = () => {
    if (selected.size === posts.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(posts.map((p) => p.id)))
    }
  }

  const handleSearch = async () => {
    if (roles.size === 0) {
      setError('Select at least one role')
      return
    }
    setSearching(true)
    setError(null)
    setPosts([])
    setSelected(new Set())
    try {
      const result = await findLinkedInJobs([...roles], 30, timePeriod, experienceRange)
      setPosts(result.posts || [])
      setSearchProvider(result.search_provider || null)
      setSearched(true)
      const withEmail = (result.posts || []).filter((p) => p.has_email)
      setSelected(new Set(withEmail.map((p) => p.id)))
    } catch (e) {
      setError(e.message)
    } finally {
      setSearching(false)
    }
  }

  const handleImport = async () => {
    const toImport = posts.filter((p) => selected.has(p.id))
    if (toImport.length === 0) return

    setImporting(true)
    setError(null)
    try {
      const result = await importLinkedInPosts(toImport, generateOptions())
      onImported(result)
      // Keep other search results — only remove successfully imported ones
      const importedUrls = new Set(
        (result.jobs || []).map((j) => j.source_url).filter(Boolean),
      )
      setPosts((prev) => prev.filter((p) => !importedUrls.has(p.url) && !selected.has(p.id)))
      setSelected(new Set())
    } catch (e) {
      setError(e.message)
    } finally {
      setImporting(false)
    }
  }

  const handleEnrich = async (post) => {
    if (!post.url) return
    setEnrichingId(post.id)
    setError(null)
    try {
      const result = await enrichLinkedInPost(post.url, post.snippet || '')
      if (result.post) {
        setPosts((prev) => prev.map((p) => (p.id === post.id ? { ...p, ...result.post, id: p.id } : p)))
        if (result.post.has_email) {
          setSelected((prev) => new Set(prev).add(post.id))
        }
      } else if (result.recruiter_email) {
        setPosts((prev) => prev.map((p) => (
          p.id === post.id
            ? { ...p, recruiter_email: result.recruiter_email, has_email: true }
            : p
        )))
        setSelected((prev) => new Set(prev).add(post.id))
      } else {
        setError(result.error || 'Could not find email on public page — paste post text instead')
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setEnrichingId(null)
    }
  }

  const handlePaste = async () => {
    if (!pasteText.trim() && !pasteUrl.trim()) {
      setError('Paste LinkedIn post text and/or URL')
      return
    }
    setPasting(true)
    setError(null)
    try {
      const result = await pasteLinkedInPost({
        text: pasteText,
        url: pasteUrl || undefined,
        auto_generate: true,
        sender: settings?.sender,
        template: settings?.template,
        candidate: settings?.candidate,
      })
      onImported({
        jobs: result.job ? [result.job] : [],
        count: 1,
        generated: result.generated ? 1 : 0,
        skipped_duplicate_url: 0,
        skipped_duplicate_email: 0,
      })
      setPasteText('')
      setPasteUrl('')
    } catch (e) {
      setError(e.message)
    } finally {
      setPasting(false)
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div>
          <h2 style={styles.title}>Find LinkedIn Posts</h2>
          <p style={styles.subtitle}>
            India HR/recruiter hiring posts — roles, posted time, and experience filters
          </p>
        </div>
        <button
          className="btn-primary"
          onClick={handleSearch}
          disabled={disabled || searching || roles.size === 0}
        >
          {searching ? 'Searching...' : 'Search LinkedIn Posts'}
        </button>
      </div>

      <div style={styles.filters}>
        <span style={styles.filterLabel}>Posted:</span>
        {TIME_PERIODS.map((p) => (
          <label
            key={p.value}
            className="inline-label"
            style={{
              ...styles.periodChip,
              ...(timePeriod === p.value ? styles.periodChipActive : {}),
            }}
          >
            <input
              type="radio"
              name="timePeriod"
              checked={timePeriod === p.value}
              onChange={() => setTimePeriod(p.value)}
            />
            {p.label}
          </label>
        ))}
      </div>

      <div style={styles.filters}>
        <span style={styles.filterLabel}>Experience:</span>
        {EXPERIENCE_OPTIONS.map((p) => (
          <label
            key={p.value}
            className="inline-label"
            style={{
              ...styles.periodChip,
              ...(experienceRange === p.value ? styles.periodChipActive : {}),
            }}
          >
            <input
              type="radio"
              name="experienceRange"
              checked={experienceRange === p.value}
              onChange={() => setExperienceRange(p.value)}
            />
            {p.label}
          </label>
        ))}
      </div>

      <div style={styles.filters}>
        <span style={styles.filterLabel}>Roles:</span>
        {DEFAULT_ROLES.map((role) => (
          <label key={role} className="inline-label" style={styles.roleChip}>
            <input
              type="checkbox"
              checked={roles.has(role)}
              onChange={() => toggleRole(role)}
            />
            {role}
          </label>
        ))}
      </div>

      <p style={styles.note}>
        Import auto-generates emails when recruiter email is found. Missing emails are auto-enriched from the public post page when possible.
        Duplicates (URL/email) are skipped.
        {searchProvider && (
          <> Search via <strong>{searchProvider === 'serpapi' ? 'SerpAPI' : 'DuckDuckGo'}</strong>.</>
        )}
        {' '}
        <a href="http://localhost:8000/api/find-jobs/bookmarklet" target="_blank" rel="noreferrer" style={styles.helpLink}>
          LinkedIn bookmarklet setup →
        </a>
      </p>

      <div style={styles.pasteBox}>
        <h3 style={styles.pasteTitle}>Paste post (when email missing from search)</h3>
        <input
          type="url"
          placeholder="LinkedIn post URL (optional)"
          value={pasteUrl}
          onChange={(e) => setPasteUrl(e.target.value)}
          style={styles.pasteInput}
        />
        <textarea
          placeholder="Paste full LinkedIn post text here (Ctrl+A on post → copy). Include email if visible."
          value={pasteText}
          onChange={(e) => setPasteText(e.target.value)}
          rows={4}
          style={styles.pasteArea}
        />
        <button
          className="btn-secondary"
          onClick={handlePaste}
          disabled={disabled || pasting || (!pasteText.trim() && !pasteUrl.trim())}
        >
          {pasting ? 'Adding...' : 'Add pasted post & generate'}
        </button>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {searched && posts.length === 0 && !searching && (
        <div style={styles.empty}>
          No matching posts found. Try another time/experience filter, or paste a post above.
        </div>
      )}

      {posts.length > 0 && (
        <>
          <div style={styles.resultsHeader}>
            <label className="inline-label" style={styles.selectAll}>
              <input
                type="checkbox"
                checked={selected.size === posts.length && posts.length > 0}
                onChange={selectAll}
              />
              Select all ({posts.length} found, {selected.size} selected)
            </label>
            <button
              className="btn-primary"
              onClick={handleImport}
              disabled={importing || selected.size === 0}
              style={{ background: '#16a34a' }}
            >
              {importing
                ? 'Importing & generating...'
                : `Import & Generate (${selected.size})`}
            </button>
          </div>

          <div style={styles.list}>
            {posts.map((post) => (
              <div
                key={post.id}
                style={{
                  ...styles.card,
                  borderColor: selected.has(post.id) ? 'var(--accent)' : 'var(--border)',
                }}
              >
                <label className="inline-check" style={styles.cardRow}>
                  <input
                    type="checkbox"
                    checked={selected.has(post.id)}
                    onChange={() => togglePost(post.id)}
                  />
                  <div style={styles.cardBody}>
                    <div style={styles.cardMeta}>
                      {post.role && <span style={styles.badge}>{post.role}</span>}
                      {post.company && <span style={styles.badgeMuted}>{post.company}</span>}
                      {post.experience_required && (
                        <span style={styles.badgeMuted}>{post.experience_required}</span>
                      )}
                      {post.has_email ? (
                        <span style={styles.badgeEmail}>✓ Email found</span>
                      ) : (
                        <span style={styles.badgeWarn}>No email — paste post text</span>
                      )}
                      {post.is_hr_post && <span style={styles.badgeHr}>HR/Recruiter</span>}
                      <span style={styles.score}>{Math.round(post.score * 100)}% match</span>
                    </div>

                    <a
                      href={post.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={styles.link}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {truncate(post.title || post.url, 100)}
                    </a>

                    {post.recruiter_email && (
                      <p style={styles.email}>{post.recruiter_email}</p>
                    )}

                    {post.snippet && (
                      <p style={styles.snippet}>{truncate(post.snippet, 280)}</p>
                    )}

                    {!post.has_email && post.url && (
                      <button
                        type="button"
                        className="btn-secondary"
                        style={{ marginTop: 8, padding: '6px 12px', fontSize: 12 }}
                        disabled={enrichingId === post.id}
                        onClick={(e) => {
                          e.preventDefault()
                          e.stopPropagation()
                          handleEnrich(post)
                        }}
                      >
                        {enrichingId === post.id ? 'Fetching email...' : 'Fetch email from post'}
                      </button>
                    )}
                  </div>
                </label>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

const styles = {
  container: {
    background: 'var(--surface)',
    borderRadius: 'var(--radius)',
    border: '1px solid var(--border)',
    padding: 24,
    width: '100%',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 16,
    flexWrap: 'wrap',
    marginBottom: 16,
  },
  title: { fontSize: 18, fontWeight: 600 },
  subtitle: { fontSize: 13, color: 'var(--text-muted)', marginTop: 4 },
  filters: { display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center', marginBottom: 12 },
  filterLabel: { fontSize: 13, fontWeight: 600, color: 'var(--text-muted)' },
  roleChip: {
    fontSize: 13,
    padding: '6px 12px',
    borderRadius: 20,
    border: '1px solid var(--border)',
    background: 'var(--bg)',
  },
  periodChip: {
    fontSize: 13,
    padding: '6px 12px',
    borderRadius: 20,
    border: '1px solid var(--border)',
    background: 'var(--bg)',
  },
  periodChipActive: {
    borderColor: 'var(--accent)',
    background: 'rgba(59,130,246,0.15)',
    color: 'var(--accent)',
    fontWeight: 600,
  },
  note: { fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 },
  helpLink: { color: 'var(--accent)', marginLeft: 4 },
  pasteBox: {
    border: '1px dashed var(--border)',
    borderRadius: 10,
    padding: 16,
    marginBottom: 16,
    background: 'var(--bg)',
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },
  pasteTitle: { fontSize: 14, fontWeight: 600 },
  pasteInput: { width: '100%' },
  pasteArea: { width: '100%', resize: 'vertical', minHeight: 90 },
  error: {
    padding: 12,
    borderRadius: 8,
    background: 'rgba(239,68,68,0.1)',
    color: 'var(--error)',
    fontSize: 13,
    marginBottom: 16,
  },
  empty: {
    textAlign: 'center',
    padding: 32,
    color: 'var(--text-muted)',
    fontSize: 14,
  },
  resultsHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
    flexWrap: 'wrap',
    gap: 12,
  },
  selectAll: { fontSize: 13 },
  list: {
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
    maxHeight: '60vh',
    overflowY: 'auto',
    overflowX: 'hidden',
  },
  card: {
    border: '1px solid var(--border)',
    borderRadius: 10,
    padding: '12px 14px',
    background: 'var(--bg)',
    width: '100%',
  },
  cardRow: {
    width: '100%',
    alignItems: 'flex-start',
    gap: 12,
    cursor: 'pointer',
  },
  cardBody: { flex: 1, minWidth: 0, overflow: 'hidden' },
  cardMeta: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 8,
    alignItems: 'center',
  },
  badge: {
    fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
    background: 'rgba(59,130,246,0.15)', color: 'var(--accent)', whiteSpace: 'nowrap',
  },
  badgeMuted: {
    fontSize: 11, padding: '2px 8px', borderRadius: 4,
    background: 'var(--surface)', color: 'var(--text-muted)',
    border: '1px solid var(--border)', whiteSpace: 'nowrap',
  },
  badgeEmail: {
    fontSize: 11, padding: '2px 8px', borderRadius: 4,
    background: 'rgba(34,197,94,0.15)', color: '#4ade80', whiteSpace: 'nowrap',
  },
  badgeWarn: {
    fontSize: 11, padding: '2px 8px', borderRadius: 4,
    background: 'rgba(251,191,36,0.15)', color: '#fbbf24', whiteSpace: 'nowrap',
  },
  badgeHr: {
    fontSize: 11, padding: '2px 8px', borderRadius: 4,
    background: 'rgba(168,85,247,0.15)', color: '#c084fc', whiteSpace: 'nowrap',
  },
  score: { fontSize: 11, color: 'var(--text-muted)', marginLeft: 'auto', whiteSpace: 'nowrap' },
  link: {
    display: 'block', fontSize: 14, fontWeight: 500, color: 'var(--accent)',
    textDecoration: 'none', wordBreak: 'break-word', overflowWrap: 'anywhere', lineHeight: 1.4,
  },
  email: { fontSize: 13, color: '#4ade80', marginTop: 6, wordBreak: 'break-all' },
  snippet: {
    fontSize: 12, color: 'var(--text-muted)', marginTop: 8, lineHeight: 1.5,
    wordBreak: 'break-word', overflowWrap: 'anywhere',
  },
}
