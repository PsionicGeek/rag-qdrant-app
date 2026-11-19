import { useState } from 'react'

export default function ChatList({ chats, activeId, onSelect, onRename, onDelete }) {
  const [editingId, setEditingId] = useState(null)
  const [editingTitle, setEditingTitle] = useState('')

  function startEdit(chat) {
    setEditingId(chat.id)
    setEditingTitle(chat.title)
  }

  function commitEdit(chat) {
    const title = editingTitle.trim()
    setEditingId(null)
    if (title && title !== chat.title) onRename(chat.id, title)
  }

  if (!chats || chats.length === 0) {
    return <p className="chat-list-empty">No chats yet — start a new one.</p>
  }

  return (
    <ul className="chat-list">
      {chats.map((chat) => (
        <li
          key={chat.id}
          className={`chat-item ${chat.id === activeId ? 'active' : ''}`}
          onClick={() => onSelect(chat.id)}
          title={chat.title}
        >
          {editingId === chat.id ? (
            <input
              className="chat-item-edit"
              value={editingTitle}
              autoFocus
              onClick={(e) => e.stopPropagation()}
              onChange={(e) => setEditingTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitEdit(chat)
                if (e.key === 'Escape') setEditingId(null)
              }}
              onBlur={() => commitEdit(chat)}
              aria-label="Rename chat"
            />
          ) : (
            <>
              <span className="chat-item-title">{chat.title}</span>
              <span className="chat-item-meta">
                {chat.documents} doc{chat.documents === 1 ? '' : 's'} · {chat.points} pts
                {chat.messages > 0 && ` · ${chat.messages} msg${chat.messages === 1 ? '' : 's'}`}
              </span>
              <span className="chat-item-actions">
                <button
                  type="button" className="mini-btn" title="Rename chat"
                  onClick={(e) => { e.stopPropagation(); startEdit(chat) }}
                >✎</button>
                <button
                  type="button" className="mini-btn danger-text" title="Delete chat"
                  onClick={(e) => { e.stopPropagation(); onDelete(chat.id) }}
                >🗑</button>
              </span>
            </>
          )}
        </li>
      ))}
    </ul>
  )
}
