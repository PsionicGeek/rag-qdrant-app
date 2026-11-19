import { useRef, useState } from 'react'
import { ingestFiles as legacyIngestFiles, ingestDir as legacyIngestDir } from '../api.js'

function fmtSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/* Ingests into the ACTIVE chat when ingestFiles / ingestDir props are
   given (multi-chat App.jsx passes per-chat functions); otherwise falls
   back to the legacy Default-chat endpoints. */
export default function Upload({ onIngested, ingestFiles, ingestDir }) {
  const doIngestFiles = ingestFiles || legacyIngestFiles
  const doIngestDir = ingestDir || legacyIngestDir
  const [files, setFiles] = useState([])
  const [dataDir, setDataDir] = useState('')
  const [loading, setLoading] = useState(false)
  const [drag, setDrag] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef(null)

  function addFiles(list) {
    const picked = Array.from(list || []).filter((f) => !files.some((x) => x.name === f.name && x.size === f.size))
    if (picked.length) setFiles((prev) => [...prev, ...picked])
  }

  async function handleUpload() {
    if (files.length === 0 || loading) return
    setLoading(true); setError('')
    try {
      const result = await doIngestFiles(files)
      onIngested(`Ingested ${result.ingested_chunks} chunks from ${result.documents} document(s).`)
      setFiles([])
    } catch (err) { setError(err.message) } finally { setLoading(false) }
  }

  async function handleIngestDir() {
    if (!dataDir.trim() || loading) return
    setLoading(true); setError('')
    try {
      const result = await doIngestDir(dataDir.trim())
      onIngested(`Ingested ${result.ingested_chunks} chunks from ${result.documents} document(s).`)
    } catch (err) { setError(err.message) } finally { setLoading(false) }
  }

  return (
    <div className="upload">
      <h2>Ingest documents</h2>
      <p className="hint">PDF, TXT, MD, CSV, DOCX, XLSX, JSON. Ingesting rebuilds this chat&apos;s collection.</p>
      <div
        className={`dropzone ${drag ? 'drag' : ''}`} role="button" tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click() }}
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); addFiles(e.dataTransfer.files) }}
      >
        <b>📂 Drop files here, or click to browse</b>
        {files.length === 0 ? 'Choose documents to add to Qdrant' : `${files.length} file${files.length > 1 ? 's' : ''} ready`}
      </div>
      <input ref={inputRef} type="file" multiple accept=".pdf,.txt,.md,.csv,.docx,.xlsx,.json" style={{ display: 'none' }} onChange={(e) => { addFiles(e.target.files); e.target.value = '' }} disabled={loading} />
      {files.length > 0 && (
        <ul className="file-list">
          {files.map((f) => (
            <li key={`${f.name}-${f.size}`}><span>📄 {f.name}</span><em>{fmtSize(f.size)}</em><button type="button" aria-label={`Remove ${f.name}`} onClick={() => setFiles(files.filter((x) => x !== f))}>✕</button></li>
          ))}
        </ul>
      )}
      <button className="primary" type="button" onClick={handleUpload} disabled={loading || files.length === 0}>
        {loading ? 'Ingesting…' : `Upload & ingest${files.length ? ` (${files.length})` : ''}`}
      </button>
      <div className="divider">or ingest a folder</div>
      <div className="dir-row">
        <input type="text" value={dataDir} onChange={(e) => setDataDir(e.target.value)} placeholder="/path/to/documents" disabled={loading} aria-label="Server folder path" />
        <button type="button" onClick={handleIngestDir} disabled={loading || !dataDir.trim()}>Ingest</button>
      </div>
      {error && <p className="error-text" role="alert">{error}</p>}
    </div>
  )
}
