export type DocumentInfo = {
  document_id: string
  revision: string
  filename: string
  media_type: string
  chunks: number
  bytes: string
  processing: boolean
}
export type Job = {
  job_id: string
  document_id: string
  filename?: string
  stage: string
  last_failure: unknown
}
export type Evidence = {
  filename?: string
  id: string
  key: { document_id: string; revision: string; chunk_id: string }
  text: string
  sources: unknown[]
  labels: string[]
  record_text?: string
}
export type Fact = {
  name: string
  value_text: string
  kind: string
  evidence_id: string
  quote: string
  pointer?: string
}
export type Answer = {
  outcome: 'supported' | 'ambiguous' | 'insufficient_evidence' | 'rejected'
  message?: string
  fields: Fact[]
  evidence: Evidence[]
  formatted?: string
  draft_text?: string
  workflow: {
    timings_ms?: Record<string, number>
    search_text?: string
    evidence_count?: number
    generation?: string
    planning?: string
    details?: string
    validation?: unknown
  }
  raw_report: string
}
export type Exchange = {
  id: string
  question: string
  answer?: Answer
  error?: string
  pending?: boolean
}
export type Conversation = {
  id: string
  created: string
  scope: string[]
  exchanges: Exchange[]
}
export type Upload = {
  id: string
  filename: string
  file?: Blob
  document_id?: string
  expected_revision?: string
  record_pointer: string
  allow_partial: boolean
  state: 'queued' | 'preparing' | 'acknowledged' | 'retry'
  message?: string
  job?: Job
}
export type Workspace = {
  version: 1
  conversations: Conversation[]
  current: string
  uploads: Upload[]
  theme: 'light' | 'dark'
}
