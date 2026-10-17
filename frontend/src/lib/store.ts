import type { Conversation, Workspace } from '../types'
// Upgrade future preferences without relabelling captured turns or queued jobs.
export function migrateDefaults(state: Workspace): Workspace {
  return state.default_policy === 'nuextract-v1' ? state : {
    ...state, answer_mode: 'nuextract', default_policy: 'nuextract-v1',
  }
}
export async function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const r = indexedDB.open('vectornext-workspace', 1)
    r.onupgradeneeded = () => r.result.createObjectStore('state')
    r.onsuccess = () => resolve(r.result)
    r.onerror = () => reject(r.error)
    r.onblocked = () =>
      reject(new Error('Browser storage is blocked by another tab.'))
  })
}
export async function load(): Promise<Workspace | undefined> {
  const db = await database()
  try {
    return await new Promise((resolve, reject) => {
      const t = db.transaction('state')
      const store = t.objectStore('state')
      const r = store.get('workspace'), keys = store.getAllKeys(), values = store.getAll()
      t.oncomplete = () => {
        const state = r.result as Workspace | undefined
        if (state) for (let i = 0; i < keys.result.length; i++) {
          if (!String(keys.result[i]).startsWith('pending:')) continue
          const pending = values.result[i] as Conversation
          const chat = state.conversations.find((c) => c.id === pending.id)
          if (!chat) state.conversations.push(pending)
          else for (const turn of pending.exchanges)
            if (!chat.exchanges.some((e) => e.job_id === turn.job_id)) chat.exchanges.push(turn)
        }
        resolve(state)
      }
      t.onerror = () => reject(t.error)
    })
  } finally {
    db.close()
  }
}
// Separate atomic reservations prevent two tabs from submitting unfinished turns
// in the same conversation, even though history merging is deliberately limited.
export async function reserveTurn(state: Workspace, chatId: string) {
  const db = await database()
  try {
    await new Promise<void>((resolve, reject) => {
      const t = db.transaction('state', 'readwrite'), store = t.objectStore('state')
      const key = `pending:${chatId}`, r = store.get(key)
      let conflict = false
      r.onsuccess = () => {
        if (r.result) { conflict = true; t.abort(); return }
        const chat = state.conversations.find((c) => c.id === chatId)!
        store.put({ ...chat, exchanges: chat.exchanges.filter((e) => e.pending) }, key)
        store.put(state, 'workspace')
      }
      t.oncomplete = () => resolve()
      t.onerror = () => reject(t.error)
      t.onabort = () => reject(conflict ? new Error('This conversation already has an unfinished answer in another tab. Reload to recover it.') : t.error)
    })
  } finally { db.close() }
}
export async function releaseTurn(requestId: string) {
  const db = await database()
  try {
    await new Promise<void>((resolve, reject) => {
      const t = db.transaction('state', 'readwrite'), store = t.objectStore('state')
      const cursor = store.openCursor()
      cursor.onsuccess = () => {
        const c = cursor.result
        if (!c) return
        if (String(c.key).startsWith('pending:') && (c.value as Conversation).exchanges.some((e) => e.job_id === requestId)) c.delete()
        c.continue()
      }
      t.oncomplete = () => resolve()
      t.onerror = () => reject(t.error)
    })
  } finally { db.close() }
}
export async function save(state: Workspace) {
  const db = await database()
  try {
    await new Promise<void>((resolve, reject) => {
      const t = db.transaction('state', 'readwrite')
      t.objectStore('state').put(state, 'workspace')
      t.oncomplete = () => resolve()
      t.onerror = () => reject(t.error)
      t.onabort = () => reject(t.error)
    })
  } finally {
    db.close()
  }
}
export function download(name: string, text: string) {
  const url = URL.createObjectURL(
    new Blob([text], { type: 'application/json;charset=utf-8' }),
  )
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
