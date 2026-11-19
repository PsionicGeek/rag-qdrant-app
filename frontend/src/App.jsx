import { useCallback, useEffect, useState } from 'react'
import Chat from './components/Chat.jsx'
import ChatList from './components/ChatList.jsx'
import Upload from './components/Upload.jsx'
import {
  getHealth, getStats,
  listChats, createChat, renameChat, deleteChat,
  getMessages, clearMessages, queryChat,
  ingestChatFiles, ingestChatDir, clearChatCollection,
} from './api.js'

const ACTIVE_KEY = 'rag-active-chat'

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('rag-theme') || 'light')
  const [health, setHealth] = useState(null)
  const [healthError, setHealthError] = useState('')
  const [chats, setChats] = useState([])
  const [activeChatId, setActiveChatId] = useState(null)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState('')
  const [noticeKind, setNoticeKind] = useState('ok')
  const [showUpload, setShowUpload] = useState(false)

  useEffect(() => { localStorage.setItem('rag-theme', theme) }, [theme])

  const refreshHealth = useCallback(async () => {
    try {
      const data = await getStats().catch(() => getHealth())
      setHealth(data)
      setHealthError('')
    } catch (err) {
      setHealth(null)
      setHealthError(err.message)
    }
  }, [])

  const refreshChats = useCallback(async () => {
    const list = await listChats()
    setChats(list)
    return list
  }, [])

  const loadMessages = useCallback(async (chatId) => {
    const msgs = await getMessages(chatId)
    setMessages(msgs.map((m) => ({
      id: m.id, role: m.role, text: m.content,
      sources: m.sources || [], created_at: m.created_at,
    })))
  }, [])

  const selectChat = useCallback(async (chatId) => {
    setActiveChatId(chatId)
    localStorage.setItem(ACTIVE_KEY, chatId)
    setMessages([])
    try { await loadMessages(chatId) } catch (err) { showNotice(`Could not load history: ${err.message}`, 'error') }
  }, [loadMessages])

  function showNotice(text, kind = 'ok') { setNotice(text); setNoticeKind(kind) }

  // On load: fetch chats, create one if none, restore the last active chat.
  useEffect(() => {
    refreshHealth()
    ;(async () => {
      try {
        let list = await refreshChats()
        if (list.length === 0) {
          const chat = await createChat()
          list = await refreshChats()
          await selectChat(chat.id)
          return
        }
        const saved = localStorage.getItem(ACTIVE_KEY)
        const target = list.find((c) => c.id === saved) || list[0]
        await selectChat(target.id)
      } catch (err) {
        showNotice(`Could not load chats: ${err.message}`, 'error')
      }
    })()
  }, [refreshHealth, refreshChats, selectChat])

  const activeChat = chats.find((c) => c.id === activeChatId) || null

  async function handleNewChat() {
    try {
      const chat = await createChat()
      await refreshChats()
      await selectChat(chat.id)
      setShowUpload(true)
    } catch (err) { showNotice(`Could not create chat: ${err.message}`, 'error') }
  }

  async function handleRename(chatId, title) {
    try {
      await renameChat(chatId, title)
      await refreshChats()
    } catch (err) { showNotice(`Rename failed: ${err.message}`, 'error') }
  }

  async function handleDeleteChat(chatId) {
    const chat = chats.find((c) => c.id === chatId)
    if (!window.confirm(`Delete chat "${chat?.title || ''}"? Its documents and Qdrant collection will be deleted too.`)) return
    try {
      await deleteChat(chatId)
      const list = await refreshChats()
      if (list.length === 0) {
        const created = await createChat()
        await refreshChats()
        await selectChat(created.id)
      } else if (chatId === activeChatId) {
        await selectChat(list[0].id)
      }
      refreshHealth()
      showNotice('Chat deleted.')
    } catch (err) { showNotice(`Delete failed: ${err.message}`, 'error') }
  }

  async function handleClearMessages() {
    if (!activeChatId) return
    try {
      await clearMessages(activeChatId)
      setMessages([])
      showNotice('Chat history cleared — documents kept.')
      await refreshChats()
    } catch (err) { showNotice(`Clear failed: ${err.message}`, 'error') }
  }

  async function handleClearCollection() {
    if (!activeChat) return
    if (!window.confirm(`Empty this chat's collection ("${activeChat.title}")? This deletes its ingested documents.`)) return
    try {
      await clearChatCollection(activeChat.id)
      showNotice('Collection cleared for this chat.')
      await refreshChats()
      refreshHealth()
    } catch (err) { showNotice(`Clear failed: ${err.message}`, 'error') }
  }

  return (
    <div className="app" data-theme={theme}>
      <header className="header">
        <div className="header-inner">
          <div className="brand">
            <div className="logo" aria-hidden>◈</div>
            <div>
              <h1>RAG <span>· Qdrant + Groq</span></h1>
              <p className="subtitle">Multi-chat — each chat has its own documents in Qdrant</p>
            </div>
          </div>
          <div className="header-actions">
            {health ? (
              <>
                <span className={health.qdrant ? 'badge ok' : 'badge warn'}>
                  <span className="dot" />{health.qdrant ? 'Qdrant connected' : 'Qdrant offline'}
                </span>
                <span className="badge muted">{health.chats ?? chats.length} chats · {health.points} points</span>
              </>
            ) : (
              <span className="badge warn"><span className="dot" />Backend unreachable</span>
            )}
            <button className="icon-btn" type="button" title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'} aria-label="Toggle theme" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
              {theme === 'dark' ? '☀️' : '🌙'}
            </button>
          </div>
        </div>
      </header>

      {notice && (
        <div className="notice" role="status">
          <div className={`notice-inner ${noticeKind === 'error' ? 'error' : ''}`}>{notice}</div>
        </div>
      )}
      {healthError && !health && (
        <div className="notice" role="alert"><div className="notice-inner error">Backend unreachable: {healthError} — is the FastAPI server running on :8000?</div></div>
      )}

      <div className="app-shell">
        <aside className="chat-sidebar">
          <button className="new-chat-btn" type="button" onClick={handleNewChat}>+ New chat</button>
          <ChatList
            chats={chats}
            activeId={activeChatId}
            onSelect={selectChat}
            onRename={handleRename}
            onDelete={handleDeleteChat}
          />
          {activeChat && (
            <div className="sidebar-stats">
              <b>{activeChat.title}</b>
              <span>{activeChat.documents} doc{activeChat.documents === 1 ? '' : 's'} · {activeChat.points} points · {activeChat.messages} messages</span>
            </div>
          )}
        </aside>

        <main className="chat-main">
          <div className="main-toolbar">
            <h2>{activeChat?.title || 'Chat'}</h2>
            <span className="spacer" />
            <button type="button" className="ghost" onClick={() => setShowUpload(!showUpload)} disabled={!activeChatId}>
              📄 {showUpload ? 'Hide documents' : `Documents${activeChat ? ` (${activeChat.documents})` : ''}`}
            </button>
            <button type="button" className="ghost danger-text-btn" onClick={handleClearCollection} disabled={!activeChatId}>
              Clear collection
            </button>
          </div>

          {showUpload && activeChatId && (
            <section className="panel upload-panel">
              <Upload
                onIngested={(msg) => { showNotice(`${msg} (in “${activeChat?.title}”)`); refreshChats(); refreshHealth() }}
                ingestFiles={(files) => ingestChatFiles(activeChatId, files)}
                ingestDir={(dir) => ingestChatDir(activeChatId, dir)}
              />
              <p className="hint">Ingests into the active chat only — other chats are untouched.</p>
            </section>
          )}

          <section className="panel chat-panel">
            <Chat
              messages={messages}
              loading={loading}
              onAsk={async ({ question, topK }) => {
                if (!activeChatId) return
                // Optimistic user bubble; the authoritative history is
                // reloaded from SQLite right after the server replies.
                setMessages((m) => [...m, { id: `tmp-${Date.now()}`, role: 'user', text: question }])
                setLoading(true)
                try {
                  await queryChat(activeChatId, question, topK)
                  await loadMessages(activeChatId)
                  await refreshChats()
                } catch (err) {
                  await loadMessages(activeChatId).catch(() => {})
                  showNotice(`Query failed: ${err.message}`, 'error')
                } finally { setLoading(false) }
              }}
              onClearChat={handleClearMessages}
            />
          </section>
        </main>
      </div>
      <footer className="footer">FastAPI · SQLite (backend/data/app.db) · Qdrant, one collection per chat · Groq (openai/gpt-oss-20b)</footer>
    </div>
  )
}
