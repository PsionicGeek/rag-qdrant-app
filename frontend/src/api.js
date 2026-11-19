async function handleResponse(res) {
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.detail || data.message || `Request failed (${res.status})`)
  }
  return data
}

export async function getHealth() {
  const res = await fetch('/health')
  return handleResponse(res)
}

export async function getStats() {
  const res = await fetch('/api/stats')
  return handleResponse(res)
}

// -- multi-chat -------------------------------------------------------------

export async function listChats() {
  const res = await fetch('/api/chats')
  return handleResponse(res)
}

export async function createChat(title) {
  const res = await fetch('/api/chats', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(title ? { title } : {}),
  })
  return handleResponse(res)
}

export async function getChat(chatId) {
  const res = await fetch(`/api/chats/${chatId}`)
  return handleResponse(res)
}

export async function renameChat(chatId, title) {
  const res = await fetch(`/api/chats/${chatId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
  return handleResponse(res)
}

export async function deleteChat(chatId) {
  const res = await fetch(`/api/chats/${chatId}`, { method: 'DELETE' })
  return handleResponse(res)
}

export async function getMessages(chatId) {
  const res = await fetch(`/api/chats/${chatId}/messages`)
  return handleResponse(res)
}

export async function clearMessages(chatId) {
  const res = await fetch(`/api/chats/${chatId}/messages`, { method: 'DELETE' })
  return handleResponse(res)
}

export async function queryChat(chatId, query, top_k = 5) {
  const res = await fetch(`/api/chats/${chatId}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k }),
  })
  return handleResponse(res)
}

export async function ingestChatFiles(chatId, files) {
  const form = new FormData()
  for (const file of files) form.append('files', file)
  const res = await fetch(`/api/chats/${chatId}/ingest`, { method: 'POST', body: form })
  return handleResponse(res)
}

export async function ingestChatDir(chatId, data_dir) {
  const res = await fetch(`/api/chats/${chatId}/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data_dir }),
  })
  return handleResponse(res)
}

export async function clearChatCollection(chatId) {
  const res = await fetch(`/api/chats/${chatId}/collection`, { method: 'DELETE' })
  return handleResponse(res)
}

// -- legacy single-chat wrappers (Default chat on the server) --------------

export async function queryRag(query, top_k = 5) {
  const res = await fetch('/api/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k }),
  })
  return handleResponse(res)
}

export async function ingestFiles(files) {
  const form = new FormData()
  for (const file of files) form.append('files', file)
  const res = await fetch('/api/ingest', { method: 'POST', body: form })
  return handleResponse(res)
}

export async function ingestDir(data_dir) {
  const res = await fetch('/api/ingest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data_dir }),
  })
  return handleResponse(res)
}

export async function clearCollection() {
  const res = await fetch('/api/collection', { method: 'DELETE' })
  return handleResponse(res)
}
