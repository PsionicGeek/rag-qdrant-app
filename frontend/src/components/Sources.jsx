import { useState } from 'react'

function fileName(source) {
  if (!source) return 'Unknown source'
  return source.split('/').pop().split('\\').pop()
}

export default function Sources({ sources, defaultCollapsed = false }) {
  const [listCollapsed, setListCollapsed] = useState(defaultCollapsed)
  const [expanded, setExpanded] = useState(() => new Set())
  if (!sources || sources.length === 0) return null

  const allExpanded = expanded.size === sources.length
  const expandAll = () => setExpanded(new Set(sources.map((_, i) => i)))
  const collapseAll = () => setExpanded(new Set())
  const toggleOne = (i) => setExpanded((prev) => {
    const next = new Set(prev)
    if (next.has(i)) next.delete(i); else next.add(i)
    return next
  })

  return (
    <div className="sources">
      <div className="sources-head">
        <h3>Sources · {sources.length}</h3>
        <div className="sources-actions">
          <button type="button" className="mini-btn" onClick={allExpanded ? collapseAll : expandAll}>
            {allExpanded ? 'Collapse all ↑' : 'Expand all ↓'}
          </button>
          <button type="button" className="mini-btn" onClick={() => setListCollapsed(!listCollapsed)} aria-expanded={!listCollapsed}>
            {listCollapsed ? `Show sources ▸` : 'Hide sources ▾'}
          </button>
        </div>
      </div>
      {!listCollapsed && (
        <div className="source-grid">
          {sources.map((s, i) => (
            <article key={s.id || i} className={`source-card ${expanded.has(i) ? 'expanded' : ''}`}>
              <div className="source-head">
                <span aria-hidden>📄</span>
                <span className="source-file">{fileName(s.source)}</span>
                {s.page !== undefined && s.page !== null && <span className="tag">p. {s.page}</span>}
                {typeof s.score === 'number' && <span className="tag score">{s.score.toFixed(3)}</span>}
                <span style={{ flex: 1 }} />
                <button type="button" className="mini-btn" onClick={() => toggleOne(i)}>
                  {expanded.has(i) ? 'Show less ↑' : 'Read more ↓'}
                </button>
              </div>
              {typeof s.score === 'number' && (
                <div className="score-bar" title={`Relevance ${s.score.toFixed(3)}`}><i style={{ width: `${Math.max(4, Math.min(100, s.score * 100))}%` }} /></div>
              )}
              <p>{s.text}</p>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
