import { useState } from 'react'
import { findLinkedInJobs, importLinkedInPosts } from '../api'

const DEFAULT_ROLES = [
  'Java Backend Engineer',
  'Java Backend Developer',
  'Java Full Stack Developer',
  'Java Software Engineer',
  'Java Developer',
  'Software Engineer',
  'Backend Engineer',
]

function truncate(text, max = 120) {
  if (!text) return ''
  return text.length > max ? `${text.slice(0, max)}…` : text
}

export default function FindJobs({ onImported, disabled }) {
  const [roles, setRoles] = useState(new Set(DEFAULT_ROLES))
  const [posts, setPosts] = useState([])
  const [selected, setSelected] = useState(new Set())
  const [searching, setSearching] = useState(false)
  const [importing, setImporting] = useState(false)
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState(null)

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
      const result = await findLinkedInJobs([...roles], 30)
      setPosts(result.posts || [])
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
      const result = await importLinkedInPosts(toImport)
      onImported(result.jobs || [])
      setSelected(new Set())
    } catch (e) {
      setError(e.message)
    } finally {
      setImporting(false)
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div>
          <h2 style={styles.title}>Find LinkedIn Posts</h2>
          <p style={styles.subtitle}>
            Search HR/recruiter posts in India only — Java roles, 2–4 years experience
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
        Filters: India locations only, recruiter/HR hiring posts. Job-seeker posts (&quot;looking for job&quot;) are excluded.
      </p>

      {error && <div style={styles.error}>{error}</div>}

      {searched && posts.length === 0 && !searching && (
        <div style={styles.empty}>
          No matching posts found. Try again later or upload screenshots instead.
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
              {importing ? 'Importing...' : `Import Selected (${selected.size})`}
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
                        <span style={styles.badgeWarn}>No email in snippet</span>
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
  note: { fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 },
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
  cardBody: {
    flex: 1,
    minWidth: 0,
    overflow: 'hidden',
  },
  cardMeta: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 8,
    alignItems: 'center',
  },
  badge: {
    fontSize: 11,
    fontWeight: 600,
    padding: '2px 8px',
    borderRadius: 4,
    background: 'rgba(59,130,246,0.15)',
    color: 'var(--accent)',
    whiteSpace: 'nowrap',
  },
  badgeMuted: {
    fontSize: 11,
    padding: '2px 8px',
    borderRadius: 4,
    background: 'var(--surface)',
    color: 'var(--text-muted)',
    border: '1px solid var(--border)',
    whiteSpace: 'nowrap',
  },
  badgeEmail: {
    fontSize: 11,
    padding: '2px 8px',
    borderRadius: 4,
    background: 'rgba(34,197,94,0.15)',
    color: '#4ade80',
    whiteSpace: 'nowrap',
  },
  badgeWarn: {
    fontSize: 11,
    padding: '2px 8px',
    borderRadius: 4,
    background: 'rgba(251,191,36,0.15)',
    color: '#fbbf24',
    whiteSpace: 'nowrap',
  },
  badgeHr: {
    fontSize: 11,
    padding: '2px 8px',
    borderRadius: 4,
    background: 'rgba(168,85,247,0.15)',
    color: '#c084fc',
    whiteSpace: 'nowrap',
  },
  score: {
    fontSize: 11,
    color: 'var(--text-muted)',
    marginLeft: 'auto',
    whiteSpace: 'nowrap',
  },
  link: {
    display: 'block',
    fontSize: 14,
    fontWeight: 500,
    color: 'var(--accent)',
    textDecoration: 'none',
    wordBreak: 'break-word',
    overflowWrap: 'anywhere',
    lineHeight: 1.4,
  },
  email: {
    fontSize: 13,
    color: '#4ade80',
    marginTop: 6,
    wordBreak: 'break-all',
  },
  snippet: {
    fontSize: 12,
    color: 'var(--text-muted)',
    marginTop: 8,
    lineHeight: 1.5,
    wordBreak: 'break-word',
    overflowWrap: 'anywhere',
  },
}
