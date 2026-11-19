import { useState } from 'react'

/* Lightweight structured-markdown renderer — no new dependency.
   Supports: ## / ### headings, **bold**, *italic*, `code`, ``` code
   blocks, - / * bullet lists, 1. numbered lists, > quotes, and
   plain paragraphs. Falls back to plain text for anything else. */

function renderInline(text, keyPrefix) {
  // Split on **bold**, *italic*, `code` — keep delimiters, render safe React nodes.
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g).filter(Boolean)
  return parts.map((part, i) => {
    const key = `${keyPrefix}-${i}`
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={key}>{part.slice(2, -2)}</strong>
    if (part.startsWith('`') && part.endsWith('`')) return <code key={key}>{part.slice(1, -1)}</code>
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) return <em key={key}>{part.slice(1, -1)}</em>
    return <span key={key}>{part}</span>
  })
}

export default function Answer({ text }) {
  const [collapsed, setCollapsed] = useState(false)
  if (!text) return null
  const lines = text.split('\n')
  const blocks = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (line.startsWith('```')) {
      const code = []
      i++
      while (i < lines.length && !lines[i].startsWith('```')) { code.push(lines[i]); i++ }
      i++
      blocks.push(<pre key={`b${i}`}><code>{code.join('\n')}</code></pre>)
      continue
    }
    if (line.startsWith('### ')) { blocks.push(<h4 key={`b${i}`}>{renderInline(line.slice(4), `h${i}`)}</h4>); i++; continue }
    if (line.startsWith('## ')) { blocks.push(<h3 key={`b${i}`}>{renderInline(line.slice(3), `h${i}`)}</h3>); i++; continue }
    if (line.startsWith('# ')) { blocks.push(<h3 key={`b${i}`}>{renderInline(line.slice(2), `h${i}`)}</h3>); i++; continue }
    if (line.startsWith('> ')) { blocks.push(<blockquote key={`b${i}`}>{renderInline(line.slice(2), `q${i}`)}</blockquote>); i++; continue }
    if (/^\s*[-*]\s+/.test(line)) {
      const items = []
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) { items.push(lines[i].replace(/^\s*[-*]\s+/, '')); i++ }
      blocks.push(<ul key={`b${i}`}>{items.map((it, j) => <li key={j}>{renderInline(it, `li${i}-${j}`)}</li>)}</ul>)
      continue
    }
    if (/^\s*\d+[.)]\s+/.test(line)) {
      const items = []
      while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i])) { items.push(lines[i].replace(/^\s*\d+[.)]\s+/, '')); i++ }
      blocks.push(<ol key={`b${i}`}>{items.map((it, j) => <li key={j}>{renderInline(it, `ol${i}-${j}`)}</li>)}</ol>)
      continue
    }
    if (line.trim() === '') { i++; continue }
    blocks.push(<p key={`b${i}`}>{renderInline(line, `p${i}`)}</p>); i++
  }

  return (
    <div className="answer-md">
      <div className="answer-md-head">
        <button type="button" className="mini-btn" onClick={() => setCollapsed(!collapsed)} aria-expanded={!collapsed}>
          {collapsed ? 'Show answer ▸' : 'Hide answer ▾'}
        </button>
      </div>
      {!collapsed && blocks}
    </div>
  )
}
