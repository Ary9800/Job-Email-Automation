import { useRef, useState } from 'react'

export default function ScreenshotUpload({ onUpload, disabled }) {
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef(null)

  const handleFiles = (fileList) => {
    const files = Array.from(fileList).filter((f) => f.type.startsWith('image/'))
    if (files.length) onUpload(files)
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    handleFiles(e.dataTransfer.files)
  }

  return (
    <div
      style={{
        ...styles.dropzone,
        borderColor: dragOver ? 'var(--accent)' : 'var(--border)',
        background: dragOver ? 'rgba(59,130,246,0.08)' : 'var(--surface)',
      }}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
      onClick={() => !disabled && inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        hidden
        disabled={disabled}
        onChange={(e) => handleFiles(e.target.files)}
      />
      <div style={styles.icon}>📸</div>
      <p style={styles.text}>
        <strong>Drop job screenshots here</strong> or click to browse
      </p>
      <p style={styles.hint}>LinkedIn & Naukri posts — add as many as you want</p>
    </div>
  )
}

const styles = {
  dropzone: {
    border: '2px dashed var(--border)',
    borderRadius: 'var(--radius)',
    padding: '48px 24px',
    textAlign: 'center',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  },
  icon: { fontSize: 40, marginBottom: 12 },
  text: { fontSize: 16, marginBottom: 6 },
  hint: { fontSize: 13, color: 'var(--text-muted)' },
}
