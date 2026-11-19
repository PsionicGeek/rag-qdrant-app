import { useEffect, useRef, useState } from 'react'
import Answer from './Answer.jsx'
import Sources from './Sources.jsx'

const EXAMPLES = [
  'What is the leading cause of cancer-related death?',
  'Summarise the main findings in these documents',
  'What methods were used in the studies?',
]

export default function Chat({ messages, loading, onAsk, onClearChat }) {
  const [question, setQuestion] = useState('')
  const [topK, setTopK] = useState(5)
  const [copiedId, setCopiedId] = useState(null)
  const endRef = useRef(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages, loading])

  async function submit(q) {
    const text = (q ?? question).trim()
    if (!text || loading) return
    setQuestion('')
    await onAsk({ question: text, topK: Number(topK) })
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
  }

  async function copy(text, id) {
    try { await navigator.clipboard.writeText(text); setCopiedId(id); setTimeout(() => setCopiedId(null), 1500) } catch { /* clipboard unavailable */ }
  }

  return (
    <>
      <div className="messages" role="log" aria-live="polite">
        {messages.length === 0 && !loading && (
          <div className="empty">
            <div className="empty-icon" aria-hidden>💬</div>
            <h2>Ask your documents anything</h2>
            <p>Ingest a few files on the left, then ask a question. Answers come only from your documents, with the exact sources cited.</p>
            <div className="examples">
              {EXAMPLES.map((ex) => (
                <button key={ex} type="button" className="chip" onClick={() => submit(ex)}>{ex}</button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`message ${m.role}`}>
            <div className="avatar" aria-hidden>{m.role === 'user' ? 'You' : '✦'}</div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div className="bubble">
                {m.error ? `Something went wrong: ${m.error}` : m.role === 'assistant' ? <Answer text={m.text} /> : m.text}
              </div>
              {m.role === 'assistant' && !m.error && m.text && (
                <div className="message-meta">
                  <button type="button" className="mini-btn" onClick={() => copy(m.text, m.id)}>{copiedId === m.id ? '✓ Copied' : '⧉ Copy answer'}</button>
                  {m.sources?.length > 0 && <span>· {m.sources.length} source{m.sources.length > 1 ? 's' : ''}</span>}
                </div>
              )}
              {m.role === 'assistant' && m.sources?.length > 0 && <Sources sources={m.sources} />}
            </div>
          </div>
        ))}
        {loading && (
          <div className="message assistant">
            <div className="avatar" aria-hidden>✦</div>
            <div className="bubble typing" aria-label="Thinking"><i /><i /><i /></div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form className="chat-form" onSubmit={(e) => { e.preventDefault(); submit() }}>
        <label className="sr-only" htmlFor="question">Ask a question</label>
        <textarea
          id="question" value={question} rows={3}
          onChange={(e) => setQuestion(e.target.value)} onKeyDown={handleKeyDown}
          placeholder="Ask a question about your documents…" disabled={loading}
        />
        <div className="chat-controls">
          <label>Top K
            <select value={topK} onChange={(e) => setTopK(e.target.value)} disabled={loading}>
              {[1, 2, 3, 4, 5, 6, 8, 10].map((n) => <option key={n} value={n}>{n} chunks</option>)}
            </select>
          </label>
          <span className="kbd-hint">Enter to send · Shift+Enter for a new line</span>
          <span className="spacer" />
          {messages.length > 0 && <button type="button" className="ghost" onClick={onClearChat} disabled={loading}>Clear chat</button>}
          <button type="submit" disabled={loading || !question.trim()}>{loading ? 'Searching…' : 'Ask →'}</button>
        </div>
      </form>
    </>
  )
}
