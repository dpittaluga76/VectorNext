import { test, expect } from '@playwright/test'

const exact = '9007199254740993.00000000000001'
const url = process.env.VECTORNEXT_HTTP_URL
test.describe('production Axum API documentation with synthetic processor', () => {
  test.skip(!url, 'requires explicitly isolated T19 API; no real inference')
  test('offline docs execute JSON and multipart requests and preserve exact text', async ({
    page,
  }) => {
    const errors: string[] = []
    const external: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    page.on('request', (r) => {
      if (new URL(r.url()).origin !== url) external.push(r.url())
    })
    await page.goto(url + '/docs')
    await expect(
      page.getByRole('heading', { name: 'VectorNext API', exact: true }),
    ).toBeVisible()
    const library = page.locator('#operations-Browser-library')
    await library.locator('.opblock-summary').click()
    await library.getByRole('button', { name: 'Try it out' }).click()
    await library.getByRole('button', { name: 'Execute', exact: true }).click()
    await expect(page.locator('#raw-response')).toContainText('documents')

    const upload = page.locator('#operations-Browser-upload')
    await upload.locator('.opblock-summary').click()
    await upload.getByRole('button', { name: 'Try it out' }).click()
    const identity = 't19-docs-' + Date.now()
    await upload
      .locator('textarea, input[type="text"]')
      .filter({ visible: true })
      .last()
      .fill(JSON.stringify({ upload_id: identity, filename: 'exact.json' }))
    await upload.locator('input[type=file]').setInputFiles({
      name: 'exact.json',
      mimeType: 'application/json',
      buffer: Buffer.from(`[{"amount":${exact},"zero":0,"unknown":null}]`),
    })
    await upload.getByRole('button', { name: 'Execute', exact: true }).click()
    await expect(page.locator('#raw-response')).toContainText('ui-' + identity)
    await expect
      .poll(async () => {
        const response = await page.request.get(url + '/v1/ui/library')
        return (await response.json()).documents.some(
          (d: { document_id: string }) => d.document_id === 'doc-' + identity,
        )
      })
      .toBe(true)

    const ask = page.locator('#operations-Retrieval-ask')
    await ask.locator('.opblock-summary').click()
    await ask.getByRole('button', { name: 'Try it out' }).click()
    const exactRequest = JSON.stringify({
      request: {
        question: 'Read the exact fixture values',
        scope: 'structured_lookup',
        filter: {
          All: [
            { DocumentIds: ['doc-' + identity] },
            {
              Attribute: {
                key: 'record',
                pointer: '/amount',
                predicate: { Eq: 'EXACT_NUMBER' },
                trust: 'SourceOrDeterministic',
              },
            },
          ],
        },
        fields: {
          amount: { kind: 'number', pointer: '/amount' },
          zero: { kind: 'integer', pointer: '/zero' },
          unknown: { kind: 'integer', nullable: true, pointer: '/unknown' },
        },
      },
    }).replace('"EXACT_NUMBER"', exact)
    await ask.locator('textarea').fill(exactRequest)
    const sentRequest = page.waitForRequest((r) => r.url().endsWith('/v1/ask'))
    await ask.getByRole('button', { name: 'Execute', exact: true }).click()
    expect((await sentRequest).postData()).toContain(`"Eq":${exact}`)
    await expect(page.locator('#raw-response')).toContainText(
      `"value":${exact}`,
    )
    await expect(ask.locator('.exact-response-body')).toContainText(exact)
    const downloadEvent = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Download exact response' }).click()
    const download = await downloadEvent
    const stream = await download.createReadStream()
    let saved = ''
    for await (const chunk of stream!) saved += chunk
    expect(saved).toContain(`"value":${exact}`)
    expect(saved).toContain('"value":null')
    expect(saved).toContain('"value":0')
    expect(errors).toEqual([])
    expect(external).toEqual([])
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: 'test-results/docs.png' })
  })

  test('workspace calls the real Axum adapter and keeps exact evidence after reload', async ({
    page,
  }) => {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    await page.goto(url!)
    await expect(page.getByRole('link', { name: 'API docs' })).toHaveAttribute(
      'href',
      '/docs',
    )
    const filename = 'browser-exact-' + Date.now() + '.json'
    await page.getByLabel('Upload documents', { exact: true }).setInputFiles({
      name: filename,
      mimeType: 'application/json',
      buffer: Buffer.from(`[{"amount":${exact}}]`),
    })
    await expect(page.getByLabel(filename, { exact: true })).toBeVisible()
    await page.getByLabel(filename, { exact: true }).check()
    await page
      .getByLabel('Ask a question', { exact: true })
      .fill('What is the amount?')
    await page
      .getByRole('button', { name: 'Ask question', exact: true })
      .click()
    await expect(page.getByText(exact, { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Source E1 for amount' }).click()
    await expect(page.locator('blockquote')).toContainText(exact)
    await page.reload()
    await expect(page.getByText(exact, { exact: true })).toBeVisible()
    expect(errors).toEqual([])
  })
})
