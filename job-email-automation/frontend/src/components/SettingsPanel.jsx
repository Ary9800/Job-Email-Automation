import { useState } from 'react'

export default function SettingsPanel({ settings, configLoaded, onChange, onResumeUpload, defaultTemplate }) {
  const [tab, setTab] = useState('profile')

  const envNote = settings.fromEnv ? (
    <p style={styles.envBanner}>
      Loaded from <code>backend/.env</code> — edit that file to change permanently.
    </p>
  ) : null

  const update = (section, field, value) => {
    onChange({
      ...settings,
      [section]: { ...(settings[section] || {}), [field]: value },
    })
  }

  const updateTemplate = (field, value) => {
    onChange({
      ...settings,
      template: { ...settings.template, [field]: value },
    })
  }

  return (
    <div>
      <h2 style={styles.title}>Settings</h2>
      {configLoaded && envNote}

      <div style={styles.tabs}>
        {['profile', 'smtp', 'template'].map((t) => (
          <button
            key={t}
            style={{
              ...styles.tab,
              background: tab === t ? 'var(--accent)' : 'transparent',
              color: tab === t ? 'white' : 'var(--text-muted)',
            }}
            onClick={() => setTab(t)}
          >
            {t === 'profile' ? 'Profile' : t === 'smtp' ? 'Email' : 'Template'}
          </button>
        ))}
      </div>

      {tab === 'profile' && (
        <div>
          <div className="form-group">
            <label>Your Name</label>
            <input
              value={settings.sender.name}
              onChange={(e) => update('sender', 'name', e.target.value)}
              placeholder="John Doe"
            />
          </div>
          <div className="form-group">
            <label>Your Email</label>
            <input
              type="email"
              value={settings.sender.email}
              onChange={(e) => update('sender', 'email', e.target.value)}
              placeholder="john@gmail.com"
            />
          </div>
          <div className="form-group">
            <label>Phone</label>
            <input
              value={settings.sender.phone}
              onChange={(e) => update('sender', 'phone', e.target.value)}
              placeholder="+91-9876543210"
            />
          </div>
          <div className="form-group">
            <label>Resume</label>
            {settings.resumeDisplayName ? (
              <p style={styles.resumeName}>✓ {settings.resumeDisplayName} (from .env)</p>
            ) : (
              <p style={styles.resumeHint}>Set DEFAULT_RESUME_PATH in backend/.env</p>
            )}
            <p style={styles.resumeOverride}>Or upload a different resume for this session:</p>
            <input
              type="file"
              accept=".pdf,.doc,.docx"
              onChange={(e) => e.target.files[0] && onResumeUpload(e.target.files[0])}
            />
          </div>
          <hr style={styles.divider} />
          <p style={styles.sectionHint}>
            AI uses this to tailor emails to each job post's requirements.
          </p>
          <div className="form-group">
            <label>Current Role</label>
            <input
              value={settings.candidate?.current_role || ''}
              onChange={(e) => update('candidate', 'current_role', e.target.value)}
              placeholder="e.g. Senior Java Developer"
            />
          </div>
          <div className="form-group">
            <label>Years of Experience</label>
            <input
              value={settings.candidate?.years_experience || ''}
              onChange={(e) => update('candidate', 'years_experience', e.target.value)}
              placeholder="e.g. 5 years"
            />
          </div>
          <div className="form-group">
            <label>Key Skills</label>
            <input
              value={settings.candidate?.key_skills || ''}
              onChange={(e) => update('candidate', 'key_skills', e.target.value)}
              placeholder="e.g. Java, Spring Boot, Microservices, AWS"
            />
          </div>
          <div className="form-group">
            <label>Experience Summary</label>
            <textarea
              rows={4}
              value={settings.candidate?.experience_summary || ''}
              onChange={(e) => update('candidate', 'experience_summary', e.target.value)}
              placeholder="Brief summary of your background, achievements, and domains..."
              style={{ resize: 'vertical' }}
            />
          </div>
        </div>
      )}

      {tab === 'smtp' && (
        <div>
          <p style={styles.smtpHint}>
            Configured in <code>backend/.env</code>. For Gmail, use an App Password.
          </p>
          <div className="form-group">
            <label>SMTP Host</label>
            <input
              value={settings.smtp.host}
              onChange={(e) => update('smtp', 'host', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>SMTP Port</label>
            <input
              type="number"
              value={settings.smtp.port}
              onChange={(e) => update('smtp', 'port', parseInt(e.target.value, 10))}
            />
          </div>
          <div className="form-group">
            <label>SMTP User</label>
            <input
              value={settings.smtp.user}
              onChange={(e) => update('smtp', 'user', e.target.value)}
              placeholder="your.email@gmail.com"
            />
          </div>
          <div className="form-group">
            <label>SMTP Password / App Password</label>
            <input
              type="password"
              value={settings.smtp.password}
              onChange={(e) => update('smtp', 'password', e.target.value)}
            />
          </div>
        </div>
      )}

      {tab === 'template' && (
        <div>
          <p style={styles.smtpHint}>
            Placeholders: {'{role}'}, {'{company}'}, {'{recruiter_name}'}, {'{experience_summary}'}, {'{sender_name}'}
          </p>
          <div className="form-group">
            <label>Subject Template</label>
            <input
              value={settings.template.subject_template}
              onChange={(e) => updateTemplate('subject_template', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Email Body Template</label>
            <textarea
              rows={12}
              value={settings.template.body_template}
              onChange={(e) => updateTemplate('body_template', e.target.value)}
              style={{ resize: 'vertical' }}
            />
          </div>
          <button
            className="btn-secondary"
            style={{ width: '100%', marginTop: 8 }}
            onClick={() => onChange({ ...settings, template: defaultTemplate })}
          >
            Reset to Default
          </button>
        </div>
      )}
    </div>
  )
}

const styles = {
  title: { fontSize: 18, fontWeight: 600, marginBottom: 16 },
  tabs: { display: 'flex', gap: 4, marginBottom: 20 },
  tab: {
    flex: 1,
    padding: '8px 4px',
    fontSize: 12,
    borderRadius: 6,
    border: 'none',
    textTransform: 'capitalize',
  },
  smtpHint: { fontSize: 12, color: 'var(--text-muted)', marginBottom: 16, lineHeight: 1.5 },
  sectionHint: { fontSize: 12, color: 'var(--accent)', marginBottom: 12, lineHeight: 1.5 },
  divider: { border: 'none', borderTop: '1px solid var(--border)', margin: '16px 0' },
  envBanner: {
    fontSize: 12,
    color: 'var(--success)',
    background: 'rgba(34,197,94,0.1)',
    padding: '8px 10px',
    borderRadius: 6,
    marginBottom: 12,
    lineHeight: 1.5,
  },
  resumeHint: { fontSize: 12, color: 'var(--warning)', marginTop: 4 },
  resumeOverride: { fontSize: 11, color: 'var(--text-muted)', marginTop: 10, marginBottom: 4 },
  resumeName: { fontSize: 12, color: 'var(--success)', marginTop: 6 },
}
