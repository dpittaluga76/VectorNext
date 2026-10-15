import { test, expect, type Page } from '@playwright/test'
const exact = '9007199254740993.00000000000001'

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
async function backend(page: Page) {
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
    const data = body?.startsWith('{') ? JSON.parse(body) : {}
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
    if (path === '/v1/ui/ask')
      return r.fulfill({
        json: {
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
          },
          raw_report: `{"value":${exact}}`,
        },
      })
    return r.fulfill({
      status: 404,
      json: { error: { message: 'Unknown mocked endpoint' } },
    })
  })
  return { count: () => uploadCount }
}
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
