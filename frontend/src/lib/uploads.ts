import type { Job, Upload } from '../types'
import { api, ApiError, delay, request } from './api'
type Status = { state: 'preparing' | 'acknowledged' | 'absent'; job?: Job }
export const reconcile = (id: string) =>
  api<Status>('/v1/ui/upload-status', { upload_id: id })
export async function transfer(
  upload: Upload,
  onState: (change: Partial<Upload>) => void,
) {
  if (!upload.file)
    throw new Error('Choose the file again to retry this upload.')
  const form = new FormData()
  form.append(
    'metadata',
    JSON.stringify({
      upload_id: upload.id,
      filename: upload.filename,
      document_id: upload.document_id,
      expected_revision: upload.expected_revision,
      record_pointer: upload.record_pointer,
      allow_partial: upload.allow_partial,
    }),
  )
  form.append('file', upload.file, upload.filename)
  for (let attempt = 0; attempt < 4; attempt++) {
    // Reconcile every submission, including explicit retries after a lost connection.
    const state = await reconcile(upload.id)
    if (state.state === 'acknowledged') {
      onState({
        state: 'acknowledged',
        job: state.job,
        file: undefined,
        message: undefined,
      })
      return
    }
    if (state.state === 'preparing') {
      onState({
        state: 'preparing',
        message:
          'Server is preparing this upload. Checking for durable acknowledgement…',
      })
      return
    }
    onState({
      state: 'preparing',
      message: upload.filename.toLowerCase().endsWith('.pdf')
        ? 'Preparing PDF on the CPU; no durable job acknowledged yet.'
        : 'Sending document; awaiting durable acknowledgement.',
    })
    try {
      const job = await request<Job>('/v1/ui/upload', form)
      onState({
        state: 'acknowledged',
        job,
        file: undefined,
        message: undefined,
      })
      return
    } catch (error) {
      if (error instanceof ApiError && error.code === 'busy' && attempt < 3) {
        onState({
          message: `Server is busy. Retry ${attempt + 1} of 3 after checking upload status.`,
        })
        await delay(2000 * 2 ** attempt)
        continue
      }
      if (!(error instanceof ApiError)) {
        try {
          const known = await reconcile(upload.id)
          if (known.state === 'acknowledged') {
            onState({
              state: 'acknowledged',
              job: known.job,
              file: undefined,
              message: undefined,
            })
            return
          }
          if (known.state === 'preparing') {
            onState({
              state: 'preparing',
              message: 'Connection interrupted; preparation is still running.',
            })
            return
          }
        } catch {
          /* retain identity and file for explicit reconciliation */
        }
        throw new Error(
          'Connection interrupted; outcome is uncertain. Retry checks the saved upload identity before sending again.',
        )
      }
      throw error
    }
  }
}
