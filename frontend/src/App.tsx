import { useEffect, useRef, useState } from 'react'
import {
  ArrowUp,
  BookOpen,
  Check,
  ChevronRight,
  FileText,
  FolderOpen,
  LoaderCircle,
  Moon,
  Plus,
  Sun,
  UploadCloud,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { api } from './lib/api'
import { bytes, context } from './lib/history'
import { download, load, save } from './lib/store'
import { reconcile, transfer } from './lib/uploads'
import type {
  Answer,
  Conversation,
  DocumentInfo,
  Evidence,
  Job,
  Upload,
  Workspace,
} from './types'

const newChat = (scope: string[]): Conversation => ({
  id: crypto.randomUUID(),
  created: new Date().toISOString(),
  scope: [...scope].sort(),
  exchanges: [],
})
function initial(): Workspace {
  const chat = newChat([])
  return {
    version: 1,
    conversations: [chat],
    current: chat.id,
    uploads: [],
    theme: matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light',
  }
}
const message = (error: unknown) =>
  error instanceof Error ? error.message : String(error)
type Library = { documents: DocumentInfo[]; jobs: Job[] }
type Readiness = {
  ready: boolean
  processor?: { capabilities?: Record<string, boolean>; error?: string }
  storage?: { coordinator?: { state: string; last_error?: string } }
}
export default function App() {
  const [workspace, setWorkspace] = useState<Workspace>(initial)
  const current = useRef(workspace)
  current.current = workspace
  const [loaded, setLoaded] = useState(false),
    [storageError, setStorageError] = useState(''),
    [error, setError] = useState('')
  const [library, setLibrary] = useState<Library>({ documents: [], jobs: [] }),
    [readiness, setReadiness] = useState<Readiness>(),
    [online, setOnline] = useState(false)
  const [question, setQuestion] = useState(''),
    [asking, setAsking] = useState(false),
    [elapsed, setElapsed] = useState(0)
  const [selected, setSelected] = useState<Evidence>(),
    [sourceInfo, setSourceInfo] = useState(''),
    [sourceError, setSourceError] = useState('')
  const [sourceChoices, setSourceChoices] = useState<Evidence[]>([])
  const [remove, setRemove] = useState<DocumentInfo>(),
    [clearing, setClearing] = useState(false)
  const [recordPointer, setRecordPointer] = useState(''),
    [allowPartial, setAllowPartial] = useState(false)
  const [fieldJson, setFieldJson] = useState(''),
    [template, setTemplate] = useState(''),
    [prose, setProse] = useState(false)
  const [candidates, setCandidates] = useState(30),
    [rerank, setRerank] = useState(20),
    [primary, setPrimary] = useState(5)
  const uploading = useRef(false),
    askLock = useRef(false),
    fileInput = useRef<HTMLInputElement>(null),
    replaceInput = useRef<HTMLInputElement>(null),
    replaceTarget = useRef<DocumentInfo | undefined>(undefined)
  const saveChain = useRef(Promise.resolve())
  const [uploadEpoch, setUploadEpoch] = useState(0)
  const chat =
    workspace.conversations.find((c) => c.id === workspace.current) ??
    workspace.conversations[0]
  const activeDocument =
    selected &&
    library.documents.find(
      (d) =>
        d.document_id === selected.key.document_id &&
        d.revision === selected.key.revision,
    )
  const capabilities = readiness?.processor?.capabilities ?? {}
  const readyToAsk =
    online &&
    capabilities.embedding &&
    capabilities.reranking &&
    capabilities.generation &&
    chat.scope.length > 0 &&
    chat.scope.every((id) =>
      library.documents.some((d) => d.document_id === id),
    )
  let history: ReturnType<typeof context> = [],
    contextError = ''
  try {
    history = context(chat)
  } catch (e) {
    contextError = message(e)
  }
  useEffect(() => {
    let live = true
    load()
      .then((saved) => {
        if (live && saved?.version === 1)
          setWorkspace({
            ...saved,
            conversations: saved.conversations.map((c) => ({
              ...c,
              exchanges: c.exchanges.map((e) =>
                e.pending
                  ? {
                      ...e,
                      pending: false,
                      error:
                        'This request was interrupted. Ask again explicitly; it was not replayed.',
                    }
                  : e,
              ),
            })),
            uploads: saved.uploads.map((u) =>
              u.state === 'queued'
                ? {
                    ...u,
                    state: 'retry',
                    message:
                      'Upload was interrupted before acknowledgement. Retry will reconcile it.',
                  }
                : u,
            ),
          })
      })
      .catch((e) => live && setStorageError(message(e)))
      .finally(() => live && setLoaded(true))
    return () => {
      live = false
    }
  }, [])
  useEffect(() => {
    document.documentElement.classList.toggle(
      'dark',
      workspace.theme === 'dark',
    )
    if (!loaded) return
    saveChain.current = saveChain.current
      .then(() => save(workspace))
      .catch((e) => {
        setStorageError(message(e))
      })
  }, [workspace, loaded])
  async function refresh() {
    try {
      setLibrary(await api<Library>('/v1/ui/library'))
      setOnline(true)
    } catch {
      setOnline(false)
    }
    try {
      setReadiness(await api<Readiness>('/readyz'))
    } catch {
      setReadiness(undefined)
    }
  }
  useEffect(() => {
    void refresh()
    const timer = setInterval(() => void refresh(), 4000)
    return () => clearInterval(timer)
  }, [])
  useEffect(() => {
    if (!asking) {
      setElapsed(0)
      return
    }
    const started = Date.now()
    const timer = setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / 1000)),
      1000,
    )
    return () => clearInterval(timer)
  }, [asking])
  function changeUpload(id: string, change: Partial<Upload>) {
    setWorkspace((w) => ({
      ...w,
      uploads: w.uploads.map((u) => (u.id === id ? { ...u, ...change } : u)),
    }))
  }
  useEffect(() => {
    if (
      !loaded ||
      uploading.current ||
      workspace.uploads.some((u) => u.state === 'preparing')
    )
      return
    const upload = workspace.uploads.find((u) => u.state === 'queued')
    if (!upload) return
    uploading.current = true
    // Finish the saved identity write before any network submission.
    void saveChain.current
      .then(() => transfer(upload, (change) => changeUpload(upload.id, change)))
      .catch((e) =>
        changeUpload(upload.id, { state: 'retry', message: message(e) }),
      )
      .finally(() => {
        uploading.current = false
        setUploadEpoch((epoch) => epoch + 1)
        void refresh()
      })
  }, [workspace.uploads, loaded, uploadEpoch])
  useEffect(() => {
    if (!loaded) return
    const timer = setInterval(() => {
      if (uploading.current) return
      for (const upload of current.current.uploads.filter(
        (u) => u.state === 'preparing',
      )) {
        void reconcile(upload.id)
          .then((s) => {
            if (s.state === 'acknowledged')
              changeUpload(upload.id, {
                state: 'acknowledged',
                job: s.job,
                file: undefined,
                message: undefined,
              })
            if (s.state === 'absent')
              changeUpload(upload.id, {
                state: 'retry',
                message:
                  'No durable acknowledgement found. Retry will check again before resubmitting.',
              })
          })
          .catch(() => {})
      }
    }, 3000)
    return () => clearInterval(timer)
  }, [loaded])
  useEffect(() => {
    setSourceInfo('')
    setSourceError('')
    setSourceChoices([])
    if (!selected) return
    let live = true
    api<{
      processing_text: string
      chunks: { id: string; text: string; sources: unknown[] }[]
    }>('/v1/ui/source', {
      document_id: selected.key.document_id,
      revision: selected.key.revision,
    })
      .then((v) => {
        if (live) {
          setSourceInfo(v.processing_text)
          if (selected.id === 'Library preview')
            setSourceChoices(
              v.chunks.map((c) => ({
                ...selected,
                key: { ...selected.key, chunk_id: c.id },
                text: c.text,
                sources: c.sources,
              })),
            )
        }
      })
      .catch((e) => {
        if (live) setSourceError(message(e))
      })
    return () => {
      live = false
    }
  }, [selected])
  function startChat(scope = chat.scope) {
    const c = newChat(scope)
    setWorkspace((w) => ({
      ...w,
      current: c.id,
      conversations: [...w.conversations, c],
    }))
    setSelected(undefined)
    setQuestion('')
    setError('')
  }
  function selectScope(id: string, checked: boolean) {
    startChat(
      checked ? [...chat.scope, id] : chat.scope.filter((d) => d !== id),
    )
  }
  function addFiles(
    files: FileList | File[] | null,
    replacement?: DocumentInfo,
  ) {
    if (!files) return
    const chosen = Array.from(files)
    if (replacement && chosen.length !== 1) return
    const additions: Upload[] = []
    for (const file of chosen) {
      if (
        !/\.(txt|pdf|json)$/i.test(file.name) ||
        file.size === 0 ||
        file.size > 16 * 1024 * 1024
      ) {
        setError(
          `${file.name}: choose a nonempty TXT, PDF or JSON file up to 16 MiB.`,
        )
        continue
      }
      additions.push({
        id: crypto.randomUUID(),
        filename: file.name,
        file,
        document_id: replacement?.document_id,
        expected_revision: replacement?.revision,
        record_pointer: recordPointer,
        allow_partial: allowPartial && /\.pdf$/i.test(file.name),
        state: 'queued',
      })
    }
    setWorkspace((w) => ({ ...w, uploads: [...w.uploads, ...additions] }))
  }
  async function ask() {
    if (askLock.current) return
    setError('')
    try {
      if (!readyToAsk)
        throw new Error(
          'Select available documents and wait for the answer models to be ready.',
        )
      if (!question.trim() || bytes(question) > 4096)
        throw new Error(
          'Enter a question up to 4 KiB. Oversized turns are not shortened.',
        )
      const turns = context(chat)
      const fields = fieldJson.trim() ? JSON.parse(fieldJson) : undefined
      const chatId = chat.id,
        id = crypto.randomUUID(),
        text = question
      askLock.current = true
      setAsking(true)
      setQuestion('')
      setWorkspace((w) => ({
        ...w,
        conversations: w.conversations.map((c) =>
          c.id === chatId
            ? {
                ...c,
                exchanges: [
                  ...c.exchanges,
                  { id, question: text, pending: true },
                ],
              }
            : c,
        ),
      }))
      try {
        const answer = await api<Answer>('/v1/ui/ask', {
          question: text,
          document_ids: chat.scope,
          history: turns,
          fields,
          template: template || undefined,
          prose,
          options: { candidates, rerank_limit: rerank, primary_limit: primary },
        })
        answer.evidence = answer.evidence.map((e) => ({
          ...e,
          filename: library.documents.find(
            (d) =>
              d.document_id === e.key.document_id &&
              d.revision === e.key.revision,
          )?.filename,
        }))
        setWorkspace((w) => ({
          ...w,
          conversations: w.conversations.map((c) =>
            c.id === chatId
              ? {
                  ...c,
                  exchanges: c.exchanges.map((e) =>
                    e.id === id ? { ...e, pending: false, answer } : e,
                  ),
                }
              : c,
          ),
        }))
        if (answer.evidence[0]) setSelected(answer.evidence[0])
      } catch (e) {
        setWorkspace((w) => ({
          ...w,
          conversations: w.conversations.map((c) =>
            c.id === chatId
              ? {
                  ...c,
                  exchanges: c.exchanges.map((t) =>
                    t.id === id
                      ? { ...t, pending: false, error: message(e) }
                      : t,
                  ),
                }
              : c,
          ),
        }))
      } finally {
        askLock.current = false
        setAsking(false)
      }
    } catch (e) {
      setError(message(e))
    }
  }
  async function confirmRemove() {
    if (!remove) return
    try {
      await api('/v1/ui/remove', {
        document_id: remove.document_id,
        revision: remove.revision,
      })
      setRemove(undefined)
      await refresh()
    } catch (e) {
      setError(message(e))
      setRemove(undefined)
    }
  }
  async function retryJob(id: string) {
    try {
      await api('/v1/retry', { job_id: id })
      await refresh()
    } catch (e) {
      setError(message(e))
    }
  }
  function clearHistory() {
    const c = newChat(chat.scope)
    setWorkspace((w) => ({ ...w, conversations: [c], current: c.id }))
    setSelected(undefined)
    setClearing(false)
  }
  if (!loaded)
    return (
      <main className="loading">
        <LoaderCircle className="animate-spin" /> Opening your local workspace…
      </main>
    )
  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="VectorNext home">
          <span className="brand-mark">
            V<span>↗</span>
          </span>
          <span>
            VectorNext<small>LOCAL KNOWLEDGE WORKSPACE</small>
          </span>
        </a>
        <div className="top-actions">
          <span className={`connection ${online ? 'connected' : ''}`}>
            <i />
            {online ? 'Local connection' : 'API offline'}
          </span>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Toggle color theme"
            onClick={() =>
              setWorkspace((w) => ({
                ...w,
                theme: w.theme === 'dark' ? 'light' : 'dark',
              }))
            }
          >
            {workspace.theme === 'dark' ? <Sun /> : <Moon />}
          </Button>
        </div>
      </header>
      <div className="readiness" aria-label="System readiness">
        {['embedding', 'reranking', 'pdf', 'generation'].map((key) => (
          <span key={key}>
            <i className={capabilities[key] ? 'ok' : ''} />
            {key === 'pdf'
              ? 'PDF preparation'
              : key === 'generation'
                ? 'Local Gemma'
                : key[0].toUpperCase() + key.slice(1)}{' '}
            <b>{capabilities[key] ? 'ready' : 'unavailable / loading'}</b>
          </span>
        ))}
        <span className="readiness-note">
          Your files stay on this computer.
        </span>
      </div>
      {readiness?.storage?.coordinator?.state === 'failed' && (
        <div role="alert" className="notice error">
          Document processing stopped. Restart VectorNext.{' '}
          {readiness.storage.coordinator.last_error}
        </div>
      )}
      {storageError && (
        <div role="alert" className="notice error">
          Browser storage is unavailable: {storageError}. This session may not
          survive a reload. Export conversations before closing.
        </div>
      )}
      {error && (
        <div role="alert" className="notice error">
          {error}
          <button onClick={() => setError('')} aria-label="Dismiss message">
            ×
          </button>
        </div>
      )}
      <main className="workspace">
        <aside className="library panel" aria-label="Document library">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">YOUR COLLECTION</p>
              <h1>
                Documents <span>{library.documents.length}</span>
              </h1>
            </div>
            <FolderOpen size={20} />
          </div>
          <div
            className="dropzone"
            onDragOver={(e) => {
              e.preventDefault()
            }}
            onDrop={(e) => {
              e.preventDefault()
              addFiles(e.dataTransfer.files)
            }}
          >
            <UploadCloud size={25} />
            <p>Bring your knowledge here</p>
            <small>TXT, PDF or JSON · up to 16 MiB</small>
            <Button
              variant="outline"
              onClick={() => fileInput.current?.click()}
              disabled={!online}
            >
              Choose files
            </Button>
            <small>or drop files into this area</small>
          </div>
          <input
            ref={fileInput}
            type="file"
            multiple
            accept=".txt,.pdf,.json"
            className="sr-only"
            aria-label="Upload documents"
            onChange={(e) => {
              addFiles(e.target.files)
              e.target.value = ''
            }}
          />
          <input
            ref={replaceInput}
            type="file"
            accept=".txt,.pdf,.json"
            className="sr-only"
            aria-label="Replace document file"
            onChange={(e) => {
              addFiles(e.target.files, replaceTarget.current)
              e.target.value = ''
            }}
          />
          <details className="advanced">
            <summary>Upload options</summary>
            <label>
              JSON record pointer
              <input
                placeholder="Root (default)"
                value={recordPointer}
                onChange={(e) => setRecordPointer(e.target.value)}
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={allowPartial}
                onChange={(e) => setAllowPartial(e.target.checked)}
              />{' '}
              Allow partial PDF extraction
            </label>
            <small>
              Strict extraction is the default. Partial results may omit pages;
              warnings remain attached to the source.
            </small>
          </details>
          <div className="section-label">
            Search scope{' '}
            <button
              disabled={asking || library.documents.length === 0}
              onClick={() =>
                startChat(library.documents.map((d) => d.document_id))
              }
            >
              Select all
            </button>
          </div>
          {!library.documents.length && (
            <p className="muted empty-small">
              Published documents will appear here. Upload a file to get
              started.
            </p>
          )}
          <div className="document-list">
            {library.documents.map((doc) => (
              <article
                className={`document ${chat.scope.includes(doc.document_id) ? 'selected' : ''}`}
                key={doc.document_id}
              >
                <label className="document-title">
                  <input
                    type="checkbox"
                    checked={chat.scope.includes(doc.document_id)}
                    disabled={asking}
                    onChange={(e) =>
                      selectScope(doc.document_id, e.target.checked)
                    }
                  />
                  <FileText size={16} />
                  <span title={doc.filename}>{doc.filename}</span>
                </label>
                <small>
                  {doc.media_type.toUpperCase()} · {doc.chunks} passages{' '}
                  {doc.processing ? '· processing replacement' : ''}
                </small>
                <div className="document-actions">
                  <button
                    disabled={doc.processing || asking}
                    onClick={() => {
                      replaceTarget.current = doc
                      replaceInput.current?.click()
                    }}
                  >
                    Replace
                  </button>
                  <button
                    disabled={doc.processing || asking}
                    onClick={() => setRemove(doc)}
                  >
                    Remove
                  </button>
                  <button
                    onClick={() =>
                      void api<{
                        chunks: {
                          id: string
                          text: string
                          sources: unknown[]
                        }[]
                      }>('/v1/ui/source', {
                        document_id: doc.document_id,
                        revision: doc.revision,
                      })
                        .then((s) => {
                          const c = s.chunks[0]
                          if (c)
                            setSelected({
                              id: 'Library preview',
                              key: {
                                document_id: doc.document_id,
                                revision: doc.revision,
                                chunk_id: c.id,
                              },
                              text: c.text,
                              sources: c.sources,
                              labels: [],
                            })
                        })
                        .catch((e) => setError(message(e)))
                    }
                  >
                    Inspect
                  </button>
                </div>
              </article>
            ))}
          </div>
          {(workspace.uploads.length > 0 || library.jobs.length > 0) && (
            <section className="jobs">
              <h2>Processing</h2>
              {workspace.uploads
                .filter((u) => u.state !== 'acknowledged')
                .map((u) => (
                  <div className="job" key={u.id}>
                    <strong>{u.filename}</strong>
                    <small>
                      {u.state === 'queued'
                        ? 'Waiting for earlier uploads'
                        : (u.message ?? u.state)}
                    </small>
                    {u.state === 'retry' && (
                      <button
                        onClick={() =>
                          changeUpload(u.id, {
                            state: 'queued',
                            message: undefined,
                          })
                        }
                      >
                        Retry upload
                      </button>
                    )}
                  </div>
                ))}
              {library.jobs.map((j) => (
                <div className="job" key={j.job_id}>
                  <strong>{j.filename ?? j.document_id}</strong>
                  <small>
                    {j.last_failure
                      ? 'Saved job failed'
                      : `Durable job · ${j.stage}`}
                  </small>
                  {!!j.last_failure && (
                    <>
                      <pre>{JSON.stringify(j.last_failure, null, 2)}</pre>
                      <button onClick={() => void retryJob(j.job_id)}>
                        Retry processing
                      </button>
                    </>
                  )}
                </div>
              ))}
              {workspace.uploads
                .filter(
                  (u) =>
                    u.state === 'acknowledged' &&
                    !library.jobs.some((j) => j.job_id === u.job?.job_id),
                )
                .slice(-3)
                .map((u) => (
                  <small key={u.id} className="ack">
                    <Check size={12} />
                    {u.filename} · acknowledged
                  </small>
                ))}
            </section>
          )}
          <footer className="library-footer">
            <span>Structural context · local storage</span>
            <small>Changing scope starts a new conversation.</small>
          </footer>
        </aside>
        <section className="conversation panel" aria-label="Conversation">
          <div className="conversation-header">
            <div>
              <p className="eyebrow">ASK YOUR DOCUMENTS</p>
              <h2>From question to evidence.</h2>
            </div>
            <Button
              variant="outline"
              size="sm"
              disabled={asking}
              onClick={() => startChat()}
            >
              <Plus /> New
            </Button>
          </div>
          <div className="conversation-tools">
            <label className="sr-only" htmlFor="conversation-select">
              Saved conversations
            </label>
            <select
              id="conversation-select"
              value={chat.id}
              disabled={asking}
              onChange={(e) => {
                setWorkspace((w) => ({ ...w, current: e.target.value }))
                setSelected(undefined)
              }}
            >
              {workspace.conversations.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.exchanges[0]?.question ?? 'New conversation'} ·{' '}
                  {new Date(c.created).toLocaleDateString()}
                </option>
              ))}
            </select>
            <button
              onClick={() =>
                download(
                  'vectornext-conversations.json',
                  JSON.stringify(
                    { version: 1, conversations: workspace.conversations },
                    null,
                    2,
                  ),
                )
              }
            >
              Export
            </button>
            <button disabled={asking} onClick={() => setClearing(true)}>
              Clear history
            </button>
          </div>
          <div className="scope-note">
            {chat.scope.length} document{chat.scope.length === 1 ? '' : 's'}{' '}
            selected <span>· saved in this browser</span>
          </div>
          <div className="exchanges" aria-live="polite">
            {chat.exchanges.length === 0 && (
              <div className="welcome">
                <div className="welcome-icon">
                  <BookOpen size={28} />
                </div>
                <p className="eyebrow">ANSWERS WITH A PAPER TRAIL</p>
                <h3>
                  What would you like
                  <br />
                  to find out?
                </h3>
                <p>
                  Select documents, then ask a question.
                  <br />
                  Every supported fact links back to its source.
                </p>
                <div className="steps">
                  <span>
                    01 <b>Upload</b>
                  </span>
                  <ChevronRight size={14} />
                  <span>
                    02 <b>Ask</b>
                  </span>
                  <ChevronRight size={14} />
                  <span>
                    03 <b>Verify</b>
                  </span>
                </div>
              </div>
            )}
            {chat.exchanges.map((exchange) => (
              <article className="exchange" key={exchange.id}>
                <div className="question">
                  <small>YOU</small>
                  <p>{exchange.question}</p>
                </div>
                {exchange.pending ? (
                  <div className="working" role="status">
                    <LoaderCircle className="animate-spin" size={16} /> Awaiting
                    local answer · {elapsed}s<br />
                    The request is running; stage progress is not streamed.
                  </div>
                ) : exchange.error ? (
                  <div className="answer-error" role="alert">
                    {exchange.error}
                    <button onClick={() => setQuestion(exchange.question)}>
                      Use question again
                    </button>
                  </div>
                ) : (
                  exchange.answer && (
                    <AnswerCard
                      answer={exchange.answer}
                      onEvidence={setSelected}
                    />
                  )
                )}
              </article>
            ))}
          </div>
          <div className="composer">
            <details className="context">
              <summary>
                Context window: {history.length / 2} of 4 completed exchanges
              </summary>
              {contextError ? (
                <p className="error">{contextError}</p>
              ) : history.length ? (
                history.map((turn, i) => (
                  <p key={i}>
                    <b>{turn.role}:</b> {turn.text}
                  </p>
                ))
              ) : (
                <p>No earlier validated answers are sent.</p>
              )}
              <small>
                Only supported factual answers are included. Drafts and rejected
                answers stay out.
              </small>
            </details>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                void ask()
              }}
            >
              <label htmlFor="question" className="sr-only">
                Ask a question
              </label>
              <textarea
                id="question"
                placeholder={
                  chat.scope.length
                    ? 'Ask a question about the selected documents…'
                    : 'Select documents in the library to begin…'
                }
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault()
                    void ask()
                  }
                }}
              />
              <Button
                type="submit"
                size="icon"
                aria-label="Ask question"
                disabled={
                  asking || !readyToAsk || !question.trim() || !!contextError
                }
              >
                <ArrowUp />
              </Button>
            </form>
            <div className="composer-note">
              <span>
                {asking
                  ? `Local request running · ${elapsed}s`
                  : !online
                    ? 'API offline; captured conversations remain available.'
                    : !readyToAsk
                      ? 'Select documents; answering requires ready models.'
                      : 'Facts first. Sources always.'}
              </span>
              <span>Ctrl ↵ to ask</span>
            </div>
            <details className="advanced">
              <summary>Advanced answer controls</summary>
              <label>
                Fields (optional JSON; skips automatic planning)
                <textarea
                  placeholder={
                    '{"launch_year":{"kind":"integer","description":"Year of launch","nullable":false}}'
                  }
                  value={fieldJson}
                  onChange={(e) => setFieldJson(e.target.value)}
                />
              </label>
              <label>
                Output template
                <input
                  value={template}
                  placeholder="Optional template"
                  onChange={(e) => setTemplate(e.target.value)}
                />
              </label>
              <div className="budgets">
                {[
                  ['Candidates', candidates, setCandidates],
                  ['Rerank', rerank, setRerank],
                  ['Passages', primary, setPrimary],
                ].map(([label, value, setter]) => (
                  <label key={String(label)}>
                    {String(label)}
                    <input
                      type="number"
                      min="1"
                      max={
                        label === 'Passages'
                          ? 20
                          : label === 'Rerank'
                            ? 20
                            : 100
                      }
                      value={value as number}
                      onChange={(e) =>
                        (setter as (n: number) => void)(Number(e.target.value))
                      }
                    />
                  </label>
                ))}
              </div>
              <label className="check">
                <input
                  type="checkbox"
                  checked={prose}
                  onChange={(e) => setProse(e.target.checked)}
                />{' '}
                Include an optional prose draft
              </label>
              <small>
                Default retrieval: ranked 30 / 20 / 5. Corpus aggregation is not
                supported.
              </small>
            </details>
          </div>
        </section>
        <aside className="evidence panel" aria-label="Source evidence">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">FOLLOW THE FACTS</p>
              <h2>Source evidence</h2>
            </div>
            <BookOpen size={20} />
          </div>
          {selected ? (
            <div className="evidence-content">
              <span className="source-tag">{selected.id}</span>
              <h3>
                {selected.filename ??
                  activeDocument?.filename ??
                  selected.key.document_id}
              </h3>
              {sourceChoices.length > 1 && (
                <label className="passage-picker">
                  Browse passages
                  <select
                    aria-label="Browse document passages"
                    value={selected.key.chunk_id}
                    onChange={(e) =>
                      setSelected(
                        sourceChoices.find(
                          (s) => s.key.chunk_id === e.target.value,
                        ),
                      )
                    }
                  >
                    {sourceChoices.map((s, i) => (
                      <option key={s.key.chunk_id} value={s.key.chunk_id}>
                        Passage {i + 1} of {sourceChoices.length}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <small>
                Captured revision {selected.key.revision.slice(0, 12)}…
              </small>
              {!activeDocument && (
                <div className="notice">
                  Historical evidence. This document was replaced or removed.
                  The captured passage below is unchanged.
                </div>
              )}
              <blockquote>{selected.text}</blockquote>
              {selected.labels?.length > 0 && (
                <p>{selected.labels.join(' · ')}</p>
              )}
              <h4>Source locations</h4>
              <SourceLocations sources={selected.sources} />
              {selected.record_text && (
                <details>
                  <summary>Exact JSON record</summary>
                  <pre>{selected.record_text}</pre>
                </details>
              )}
              {activeDocument?.media_type === 'pdf' && (
                <a
                  className="source-link"
                  href={`/v1/ui/original?document_id=${encodeURIComponent(selected.key.document_id)}&revision=${selected.key.revision}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open original PDF ↗
                </a>
              )}
              {sourceError && <p className="muted">{sourceError}</p>}
              {sourceInfo && (
                <details>
                  <summary>Extraction details and warnings</summary>
                  <pre>{sourceInfo}</pre>
                </details>
              )}
            </div>
          ) : (
            <div className="evidence-empty">
              <FileText size={32} />
              <h3>A source for every fact.</h3>
              <p>
                Click a citation in an answer to see the exact passage and its
                location.
              </p>
              <small>
                Original text is kept separate from generated context.
              </small>
            </div>
          )}
        </aside>
      </main>
      <Dialog
        open={!!remove}
        onOpenChange={(open) => {
          if (!open) setRemove(undefined)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove this document?</DialogTitle>
            <DialogDescription>
              {remove?.filename} will leave the searchable collection. Captured
              conversation evidence and historical jobs remain.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRemove(undefined)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={() => void confirmRemove()}>
              Remove document
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={clearing} onOpenChange={setClearing}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Clear browser conversations?</DialogTitle>
            <DialogDescription>
              This deletes saved conversations and captured evidence in this
              browser. Export first if you need a copy. Uploaded documents
              remain.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setClearing(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={clearHistory}>
              Clear conversations
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export function AnswerCard({
  answer,
  onEvidence,
}: {
  answer: Answer
  onEvidence: (e: Evidence) => void
}) {
  const labels = {
    supported: 'Supported by sources',
    ambiguous: 'Ambiguous evidence',
    insufficient_evidence: 'Insufficient evidence',
    rejected: 'Answer rejected',
  }
  return (
    <div className={`answer ${answer.outcome}`}>
      <span className="outcome">
        {answer.outcome === 'supported' && <Check size={14} />}{' '}
        {labels[answer.outcome]}
      </span>
      {answer.message && <p>{answer.message}</p>}
      {answer.outcome === 'ambiguous' && (
        <p>
          The selected evidence does not establish a single answer. Make the
          question or document scope more specific.
        </p>
      )}
      {answer.outcome === 'insufficient_evidence' && (
        <p>
          The available passages do not support all requested facts. Try a more
          specific question or add relevant documents.
        </p>
      )}
      {answer.fields.map((f) => (
        <div className="fact" key={f.name}>
          <span>{f.name.replaceAll('_', ' ')}</span>
          <strong>{f.value_text}</strong>
          <small>{f.kind}</small>
          <button
            className="citation"
            onClick={() => {
              const e = answer.evidence.find((e) => e.id === f.evidence_id)
              if (e) onEvidence(e)
            }}
            aria-label={`Source ${f.evidence_id} for ${f.name}`}
          >
            [{f.evidence_id}] ↗
          </button>
        </div>
      ))}
      {answer.formatted && <p className="formatted">{answer.formatted}</p>}
      {answer.draft_text && (
        <details>
          <summary>
            Optional prose draft · not verified for semantic faithfulness
          </summary>
          <pre>{answer.draft_text}</pre>
        </details>
      )}
      <details className="workflow">
        <summary>How did you find this?</summary>
        <p>
          {answer.workflow.planning}. {answer.workflow.evidence_count ?? 0}{' '}
          captured passages. Outcome: {labels[answer.outcome].toLowerCase()}.
        </p>
        {answer.workflow.timings_ms && (
          <ul>
            {Object.entries(answer.workflow.timings_ms).map(([name, ms]) => (
              <li key={name}>
                {name.replaceAll('_', ' ')}{' '}
                <span>{(ms / 1000).toFixed(2)}s</span>
              </li>
            ))}
          </ul>
        )}
        <details>
          <summary>Detailed workflow and function references</summary>
          <p>{answer.workflow.details}</p>
          <pre>{JSON.stringify(answer.workflow, null, 2)}</pre>
        </details>
        <button
          onClick={() =>
            download('vectornext-diagnostics.json', answer.raw_report)
          }
        >
          Export complete diagnostics
        </button>
        <div className="source-buttons">
          {answer.evidence.map((e) => (
            <button key={e.id} onClick={() => onEvidence(e)}>
              Inspect [{e.id}]
            </button>
          ))}
        </div>
      </details>
    </div>
  )
}

function SourceLocations({ sources }: { sources: unknown[] }) {
  return (
    <div className="source-locations">
      {sources.map((source, i) => {
        const s = source as { label?: string; raw_text?: string }
        return (
          <div key={i}>
            <p>{s.label ?? 'Source location'}</p>
            <details>
              <summary>Exact location metadata</summary>
              <pre>{s.raw_text ?? JSON.stringify(source, null, 2)}</pre>
            </details>
          </div>
        )
      })}
    </div>
  )
}
