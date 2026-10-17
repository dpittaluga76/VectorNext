import { test, expect, type Page } from '@playwright/test'
const exact = '9007199254740993.00000000000001'

test('model availability, loaded model and failed answer queue are distinct', async ({ page }) => {
  await backend(page)
  await page.route('**/readyz', (r) => r.fulfill({ json: {
    ready: false, answer_queue: { ready: false, unfinished: 1, capacity: 16, error: 'saved queue failure' },
    processor: { capabilities: { embedding: true, reranking: true, pdf: true, generation: true },
      generation: { scheduler: { models: { nuextract: true, gemma: true }, loaded_model: 'nuextract' } } },
  } }))
  await page.goto('/')
  await expect(page.getByLabel('Model availability')).toContainText('NuExtract: available')
  await expect(page.getByLabel('Model availability')).toContainText('Gemma: available')
  await expect(page.getByLabel('Model availability')).toContainText('Loaded model: nuextract')
  await expect(page.getByLabel('System readiness')).toContainText('Answer queue unavailable')
  await expect(page.getByRole('alert')).toContainText('saved queue failure')
  await page.getByLabel('Observations.json').check()
  await page.getByLabel('Ask a question', { exact: true }).fill('Amount?')
  await expect(page.getByRole('button', { name: 'Ask question', exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Inspect', exact: true })).toBeEnabled()
})

test('clearing conversations keeps the document library', async ({ page }) => {
  await backend(page)
  await page.goto('/')
  await page.getByLabel('Observations.json').check()
  await page.getByLabel('Ask a question', { exact: true }).fill('Amount?')
  await page.getByRole('button', { name: 'Ask question', exact: true }).click()
  await expect(page.getByText(exact, { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Clear history', exact: true }).click()
  await page
    .getByRole('button', { name: 'Clear conversations', exact: true })
    .click()
  await expect(page.getByText(exact, { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Observations.json')).toBeVisible()
  await page.reload()
  await expect(page.getByText(exact, { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Observations.json')).toBeVisible()
})

test('library can browse every passage without answer models', async ({
  page,
}) => {
  await backend(page)
  await page.route('**/v1/ui/source', (r) =>
    r.fulfill({
      json: {
        processing_text: '{}',
        chunks: [
          { id: 'c1', text: 'First captured passage', sources: [] },
          { id: 'c2', text: 'Second captured passage', sources: [] },
        ],
      },
    }),
  )
  await page.goto('/')
  await page.getByRole('button', { name: 'Inspect', exact: true }).click()
  await page.getByLabel('Browse document passages').selectOption('c2')
  await expect(page.locator('blockquote')).toHaveText('Second captured passage')
})

test('delayed PDF preparation survives reload before durable acknowledgement', async ({
  page,
}) => {
  await backend(page)
  let state = 'absent',
    posts = 0
  await page.route('**/v1/ui/upload-status', (r) =>
    r.fulfill({
      json: {
        state,
        ...(state === 'acknowledged'
          ? { job: { job_id: 'pdf-job', stage: 'Parsed' } }
          : {}),
      },
    }),
  )
  await page.route('**/v1/ui/upload', (r) => {
    posts++
    state = 'preparing'
    return r.abort('connectionreset')
  })
  await page.goto('/')
  await page.getByLabel('Upload documents', { exact: true }).setInputFiles({
    name: 'delayed.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF test'),
  })
  await expect(
    page.getByText('Connection interrupted; preparation is still running.'),
  ).toBeVisible()
  await page.reload()
  await expect(
    page.getByText('Connection interrupted; preparation is still running.'),
  ).toBeVisible()
  expect(posts).toBe(1)
  state = 'acknowledged'
  await expect(page.getByText('delayed.pdf · acknowledged')).toBeVisible({
    timeout: 8000,
  })
  expect(posts).toBe(1)
})
test('bounded busy retries retain identity and allow explicit retry', async ({
  page,
}) => {
  await backend(page)
  const identities: string[] = []
  let busy = true
  await page.route('**/v1/ui/upload', (r) => {
    const metadata = JSON.parse(
      r
        .request()
        .postData()!
        .match(/\{"upload_id"[^\r\n]+/)![0],
    )
    identities.push(metadata.upload_id)
    return busy
      ? r.fulfill({
          status: 503,
          json: {
            error: { code: 'busy', message: 'Busy processing other work' },
          },
        })
      : r.fulfill({ status: 202, json: { job_id: 'job', stage: 'Parsed' } })
  })
  await page.goto('/')
  await page.getByLabel('Upload documents', { exact: true }).setInputFiles({
    name: 'busy.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('test'),
  })
  await expect(page.getByRole('button', { name: 'Retry upload' })).toBeVisible({
    timeout: 22000,
  })
  expect(identities).toHaveLength(4)
  expect(new Set(identities).size).toBe(1)
  busy = false
  await page.getByRole('button', { name: 'Retry upload' }).click()
  await expect(page.getByText('busy.txt · acknowledged')).toBeVisible()
  expect(identities).toHaveLength(5)
  expect(new Set(identities).size).toBe(1)
})
test('model outage keeps library and captured source inspection available', async ({
  page,
}) => {
  await backend(page)
  await page.route('**/readyz', (r) =>
    r.fulfill({
      status: 503,
      json: {
        ready: false,
        processor: {
          capabilities: {
            embedding: true,
            reranking: true,
            pdf: true,
            generation: false,
          },
        },
      },
    }),
  )
  await page.goto('/')
  await page.getByLabel('Observations.json').check()
  await page.getByLabel('Ask a question', { exact: true }).fill('Amount?')
  await expect(
    page.getByRole('button', { name: 'Ask question', exact: true }),
  ).toBeDisabled()
  await page.getByRole('button', { name: 'Inspect', exact: true }).click()
  await expect(page.locator('blockquote')).toContainText(exact)
})
async function backend(page: Page, delayed = false) {
  let docs = [
    {
      document_id: 'doc-one',
      filename: 'Observations.json',
      revision: 'revision-one',
      media_type: 'json',
      chunks: 1,
      bytes: '100',
      processing: false,
    },
  ]
  const uploads: Record<string, object> = {}
  const answerJobs: Record<string, { [key: string]: unknown }> = {}
  const submissions: { request_id: string; mode: string }[] = []
  let uploadCount = 0
  const evidence = {
    id: 'E1',
    key: { document_id: 'doc-one', revision: 'revision-one', chunk_id: 'c1' },
    text: `{"amount":${exact},"note":"<script>window.hacked=true</script>"}`,
    sources: [{ json_pointer: '/0/amount' }],
    labels: [],
    record_text: `{"amount":${exact}}`,
  }
  await page.route('**/readyz', (r) =>
    r.fulfill({
      json: {
        ready: true,
        processor: {
          capabilities: {
            embedding: true,
            reranking: true,
            generation: true,
            pdf: true,
          },
        },
      },
    }),
  )
  await page.route('**/v1/**', async (r) => {
    const path = new URL(r.request().url()).pathname
    const body = r.request().postData()
    const envelope = body?.startsWith('{') ? JSON.parse(body) : {}
    const data = path === '/v1/answer-jobs' ? envelope.payload : envelope
    if (path === '/v1/answer-jobs' && r.request().method() === 'GET') return r.fulfill({ json: { jobs: Object.values(answerJobs) } })
    if (path.startsWith('/v1/answer-jobs/')) {
      const id = path.split('/')[3]
      if (path.endsWith('/clear')) { delete answerJobs[id]; return r.fulfill({ json: { cleared: true } }) }
      if (path.endsWith('/cancel') && answerJobs[id]) Object.assign(answerJobs[id], { state: 'cancelled', terminal: true, result: undefined })
      return answerJobs[id] ? r.fulfill({ json: answerJobs[id] }) : r.fulfill({ status: 404, json: { error: { message: 'answer job not found' } } })
    }
    if (path === '/v1/ui/library')
      return r.fulfill({ json: { documents: docs, jobs: [] } })
    if (path === '/v1/ui/upload-status')
      return r.fulfill({
        json: uploads[data.upload_id]
          ? { state: 'acknowledged', job: uploads[data.upload_id] }
          : { state: 'absent' },
      })
    if (path === '/v1/ui/upload') {
      uploadCount++
      const meta = JSON.parse(body!.match(/\{"upload_id"[^\r\n]+/)![0])
      const job = {
        job_id: `ui-${meta.upload_id}`,
        document_id: meta.document_id ?? `doc-${meta.upload_id}`,
        stage: 'committed',
      }
      uploads[meta.upload_id] = job
      docs = docs.filter((d) => d.document_id !== job.document_id)
      docs.push({
        document_id: job.document_id,
        filename: meta.filename,
        revision: 'new-revision',
        media_type: meta.filename.split('.').at(-1),
        chunks: 1,
        bytes: '50',
        processing: false,
      })
      return r.fulfill({ status: 202, json: job })
    }
    if (path === '/v1/ui/source')
      return r.fulfill({
        json: {
          processing_text: '{"warnings":[]}',
          chunks: [
            { id: 'c1', text: evidence.text, sources: evidence.sources },
          ],
        },
      })
    if (path === '/v1/ui/remove') {
      docs = docs.filter((d) => d.document_id !== data.document_id)
      return r.fulfill({ json: { removed: true } })
    }
    if (path === '/v1/answer-jobs') {
      const result = {
          outcome: 'supported',
          fields: [
            {
              name: 'amount',
              kind: 'number',
              value_text: exact,
              evidence_id: 'E1',
              quote: '',
              pointer: '/amount',
            },
          ],
          evidence: [evidence],
          workflow: {
            evidence_count: 1,
            planning: 'local field planning recorded',
            timings_ms: { answer_total: 123 },
            ...(data.options?.evidence_strategy === 'facet_coverage_v1'
              ? {
                  selection_summary:
                    'Facet coverage: 1 field queries, 1 candidates, 1 planned and 1 admitted primary passages.',
                  facet_queries: ['amount: Requested exact amount'],
                  selection_functions: 'answers::facets::select()',
                }
              : {}),
          },
          raw_report: `{"value":${exact}}`,
      }
      submissions.push(envelope)
      const job = { request_id: envelope.request_id, mode: envelope.mode, terminal: !delayed, state: delayed ? 'waiting_for_gemma' : 'completed', fallback_reason: delayed ? 'insufficient_evidence' : null, created_ms: Date.now(), updated_ms: Date.now(), status_code: 200, result: delayed ? undefined : result, attempts: [], diagnostics_text: result.raw_report }
      answerJobs[envelope.request_id] = job
      return r.fulfill({ status: 202, json: job })
    }
    return r.fulfill({
      status: 404,
      json: { error: { message: 'Unknown mocked endpoint' } },
    })
  })
  return { count: () => uploadCount, submissions, jobs: answerJobs }
}

test('pending jobs recover after reload, remember mode, cancel and clear explicitly', async ({ page }) => {
  const server = await backend(page, true)
  await page.goto('/')
  await page.getByLabel('Observations.json').check()
  await expect(page.getByLabel('Answer mode', { exact: true })).toHaveValue('nuextract')
  await page.getByLabel('Answer mode', { exact: true }).selectOption('nuextract')
  await page.getByLabel('Ask a question', { exact: true }).fill('Amount?')
  await page.getByRole('button', { name: 'Ask question', exact: true }).click()
  await expect(page.getByText('Fallback: insufficient_evidence')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Ask question', exact: true })).toBeDisabled()
  await page.reload()
  await expect(page.getByText('Fallback: insufficient_evidence')).toBeVisible()
  await expect(page.getByLabel('Answer mode', { exact: true })).toHaveValue('nuextract')
  expect(server.submissions).toHaveLength(1)
  expect(server.submissions[0].mode).toBe('nuextract')
  await page.getByRole('button', { name: 'Cancel answer', exact: true }).click()
  await expect(page.locator('.answer-error')).toContainText('Job cancelled')
  await page.getByRole('button', { name: 'Answer jobs', exact: true }).click()
  await page.getByRole('button', { name: 'Inspect attempts', exact: true }).click()
  const exportEvent = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export exact diagnostics', exact: true }).click()
  const stream = await (await exportEvent).createReadStream()
  let text = ''; for await (const chunk of stream!) text += chunk.toString()
  expect(text).toContain(exact)
  await page.getByRole('button', { name: 'Clear record', exact: true }).click()
  await expect.poll(() => Object.keys(server.jobs)).toHaveLength(0)
})

test('another conversation can queue while the first turn waits', async ({ page }) => {
  const server = await backend(page, true)
  await page.goto('/')
  await page.getByLabel('Observations.json').check()
  await page.getByLabel('Ask a question', { exact: true }).fill('First amount?')
  await page.getByRole('button', { name: 'Ask question', exact: true }).click()
  await expect(page.getByText('Fallback: insufficient_evidence')).toBeVisible()
  await page.getByRole('button', { name: 'New', exact: true }).click()
  await page.getByLabel('Ask a question', { exact: true }).fill('Second amount?')
  await page.getByRole('button', { name: 'Ask question', exact: true }).click()
  await expect.poll(() => server.submissions.length).toBe(2)
  expect(new Set(server.submissions.map((s) => s.request_id)).size).toBe(2)
})
test('facet choice reaches API and recorded workflow survives reload', async ({
  page,
}) => {
  await backend(page)
  await page.goto('/')
  await page.getByLabel('Observations.json').check()
  await page.getByText('Advanced answer controls', { exact: true }).click()
  await expect(page.getByLabel('Evidence selection')).toHaveValue('ranked')
  await page.getByLabel('Evidence selection').selectOption('facet_coverage_v1')
  await page
    .getByLabel('Ask a question', { exact: true })
    .fill('What is the amount?')
  const request = page.waitForRequest((r) => r.url().endsWith('/v1/answer-jobs') && r.method() === 'POST')
  await page.getByRole('button', { name: 'Ask question', exact: true }).click()
  expect((await request).postDataJSON().payload.options.evidence_strategy).toBe(
    'facet_coverage_v1',
  )
  await expect(page.getByText(exact, { exact: true })).toBeVisible()
  await page.getByText('How did you find this?', { exact: true }).click()
  await expect(
    page.locator('p').filter({ hasText: /Facet coverage: 1 field queries/ }),
  ).toBeVisible()
  await expect(page.getByLabel('Recorded facet queries')).toHaveText(
    'amount: Requested exact amount',
  )
  await page.reload()
  await page.getByText('How did you find this?', { exact: true }).click()
  await expect(
    page.locator('p').filter({ hasText: /Facet coverage: 1 field queries/ }),
  ).toBeVisible()
  await expect(page.getByText(exact, { exact: true })).toBeVisible()
})
test('question, exact values, citations, reload, export and historical evidence', async ({
  page,
}) => {
  await backend(page)
  await page.goto('/')
  await page.getByLabel('Observations.json').check()
  await page
    .getByLabel('Ask a question', { exact: true })
    .fill('What is the amount?')
  await page.getByRole('button', { name: 'Ask question', exact: true }).click()
  await expect(page.getByText(exact, { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Source E1 for amount' }).click()
  await expect(page.locator('blockquote')).toContainText('<script>')
  expect(await page.evaluate(() => 'hacked' in window)).toBe(false)
  await page.reload()
  await expect(page.getByText(exact, { exact: true })).toBeVisible()
  await expect(
    page.getByText('Context window: 1 of 4 completed exchanges'),
  ).toBeVisible()
  await page.getByText('How did you find this?', { exact: true }).click()
  const downloadEvent = page.waitForEvent('download')
  await page
    .getByRole('button', { name: 'Export complete diagnostics' })
    .click()
  const download = await downloadEvent
  const stream = await download.createReadStream()
  let text = ''
  for await (const chunk of stream!) text += chunk
  expect(text).toBe(`{"value":${exact}}`)
  await page.getByRole('button', { name: 'Source E1 for amount' }).click()
  await page.getByRole('button', { name: 'Remove', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect(page.getByLabel('Observations.json')).toBeVisible()
  await page.getByRole('button', { name: 'Remove', exact: true }).click()
  await page
    .getByRole('button', { name: 'Remove document', exact: true })
    .click()
  await expect(
    page.getByText('Historical evidence.', { exact: false }),
  ).toBeVisible()
  await expect(page.locator('blockquote')).toContainText(exact)
  await page.screenshot({ path: 'test-results/workspace.png', fullPage: true })
})
test('sequential TXT PDF JSON uploads and replacement', async ({ page }) => {
  const server = await backend(page)
  await page.goto('/')
  await page.getByLabel('Upload documents', { exact: true }).setInputFiles([
    {
      name: 'mission.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('Launch in 1977'),
    },
    {
      name: 'mission.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF example'),
    },
    {
      name: 'mission.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{"year":1977}'),
    },
  ])
  await expect(page.getByLabel('mission.txt', { exact: true })).toBeVisible()
  await expect(page.getByLabel('mission.pdf', { exact: true })).toBeVisible()
  await expect(page.getByLabel('mission.json', { exact: true })).toBeVisible()
  expect(server.count()).toBe(3)
  await page
    .locator('article.document')
    .filter({ hasText: 'mission.txt' })
    .getByRole('button', { name: 'Replace' })
    .click({ noWaitAfter: true })
  await page.getByLabel('Replace document file').setInputFiles({
    name: 'revised.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('Revised source'),
  })
  await expect(page.getByLabel('revised.txt')).toBeVisible()
  expect(server.count()).toBe(4)
})
test('narrow layout, keyboard, theme, scope and browser storage failure', async ({
  page,
}) => {
  await backend(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => {
    const original = IDBObjectStore.prototype.put
    IDBObjectStore.prototype.put = function (...args) {
      if (args[1] === 'workspace')
        throw new DOMException('Quota exceeded', 'QuotaExceededError')
      return original.apply(this, args)
    }
  })
  await page.goto('/')
  await expect(page.getByRole('alert')).toContainText(
    'Browser storage is unavailable',
  )
  await page.getByLabel('Observations.json').focus()
  await page.keyboard.press('Space')
  await expect(page.getByText('1 document selected')).toBeVisible()
  await page.getByRole('button', { name: 'Toggle color theme' }).click()
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true)
  await page.screenshot({ path: 'test-results/narrow.png', fullPage: true })
})
test('lost acknowledgement reconciles saved identity without duplicate submission', async ({
  page,
}) => {
  await backend(page)
  let identity = '',
    posts = 0
  await page.route('**/v1/ui/upload-status', (r) =>
    r.fulfill({
      json: identity
        ? {
            state: 'acknowledged',
            job: { job_id: `ui-${identity}`, stage: 'committed' },
          }
        : { state: 'absent' },
    }),
  )
  await page.route('**/v1/ui/upload', (r) => {
    posts++
    identity = JSON.parse(
      r
        .request()
        .postData()!
        .match(/\{"upload_id"[^\r\n]+/)![0],
    ).upload_id
    return r.abort('connectionreset')
  })
  await page.goto('/')
  await page.getByLabel('Upload documents', { exact: true }).setInputFiles({
    name: 'lost.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('test'),
  })
  await expect(page.getByText('lost.txt · acknowledged')).toBeVisible()
  expect(posts).toBe(1)
  await page.reload()
  await expect(page.getByText('lost.txt · acknowledged')).toBeVisible()
  expect(posts).toBe(1)
})
