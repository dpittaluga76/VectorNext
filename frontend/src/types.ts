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
    selection_summary?: string
    facet_queries?: string[]
    selection_functions?: string
  }
  raw_report: string
}
export type Exchange = {
  id: string
  question: string
  answer?: Answer
  error?: string
  pending?: boolean
  job_id?: string
  mode?: AnswerMode
  job_state?: string
  started_ms?: number
  fallback_reason?: string
  job_request?: AnswerSubmission
}
export type AnswerMode = 'hybrid' | 'gemma' | 'nuextract'
export type AnswerSubmission = { request_id: string; mode: AnswerMode; kind: 'ui'; payload: unknown }
export type AnswerJob = {
  request_id: string; mode: AnswerMode; state: string; terminal: boolean;
  created_ms: number; updated_ms: number; fallback_reason?: string; error?: string;
  result?: Answer | { error: { message: string } }; status_code?: number;
  response_text?: string; diagnostics_text?: string;
  attempts?: { model: string; state: string; queue_ms: number; activation_ms: number; work_ms: number; response_text?: string }[]
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
  answer_mode?: AnswerMode
  default_policy?: 'nuextract-v1'
}
