import { test, expect } from '@playwright/test'
import http from 'node:http'
import { readFile, mkdir, writeFile } from 'node:fs/promises'
let proxy: http.Server
test.describe('production app with local models', () => {
  test.skip(!process.env.VECTORNEXT_LIVE_URL, 'explicit live inference opt-in')
  test.beforeAll(async () => {
    proxy = http.createServer((incoming, outgoing) => {
      const upstream = http.request(
        new URL(incoming.url!, process.env.VECTORNEXT_LIVE_URL),
        { method: incoming.method, headers: incoming.headers },
        (response) => {
          outgoing.writeHead(response.statusCode!, response.headers)
          response.pipe(outgoing)
        },
      )
      upstream.on('error', (error) => {
        outgoing.writeHead(502)
        outgoing.end(String(error))
      })
      incoming.pipe(upstream)
    })
    await new Promise<void>((resolve) => proxy.listen(4180, '0.0.0.0', resolve))
  })
  test.afterAll(async () => {
    if (proxy)
      await new Promise<void>((resolve) => proxy.close(() => resolve()))
  })
  test('upload, ordinary question, follow-up, source, reload and exact JSON', async ({
    page,
  }) => {
    test.setTimeout(360000)
    const failures: string[] = []
    page.on('pageerror', (e) => failures.push(e.message))
    const captured: unknown[] = []
    page.on('response', async (response) => {
      if (response.url().endsWith('/v1/ui/ask'))
        captured.push(await response.json())
    })
    await page.route('**/*', (route) =>
      new URL(route.request().url()).hostname === 'localhost'
        ? route.continue()
        : route.abort(),
    )
    await page.goto('http://localhost:4180')
    await expect(page.getByText('API offline', { exact: true })).toHaveCount(0)
    const filename = `Apollo-mission-${Date.now()}.txt`
    await page
      .getByLabel('Upload documents', { exact: true })
      .setInputFiles({
        name: filename,
        mimeType: 'text/plain',
        buffer: await readFile('/fixtures/apollo11.txt'),
      })
    await expect(page.getByLabel(filename, { exact: true })).toBeVisible({
      timeout: 90000,
    })
    await page.getByLabel(filename, { exact: true }).check()
    await page
      .getByLabel('Ask a question', { exact: true })
      .fill('In which year did Apollo 11 launch?')
    await page
      .getByRole('button', { name: 'Ask question', exact: true })
      .click()
    await expect(page.locator('.fact strong').last()).toHaveText('1969', {
      timeout: 120000,
    })
    await page.locator('.citation').last().click()
    await expect(page.locator('blockquote')).toContainText('1969')
    await expect(page.getByText(/TXT lines/).first()).toBeVisible()
    await page
      .getByLabel('Ask a question', { exact: true })
      .fill('Who commanded that mission?')
    await page
      .getByRole('button', { name: 'Ask question', exact: true })
      .click()
    await expect(page.locator('.fact strong').last()).toHaveText(
      'Neil Armstrong',
      { timeout: 120000 },
    )
    await page.locator('.citation').last().click()
    await page.screenshot({
      path: 'test-results/live-workspace.png',
      fullPage: true,
    })
    await page.reload()
    await expect(page.locator('.fact strong').last()).toHaveText(
      'Neil Armstrong',
    )
    await expect(
      page.getByText('Context window: 2 of 4 completed exchanges'),
    ).toBeVisible()
    await page.getByLabel(filename, { exact: true }).uncheck()
    await page.getByLabel('exact.json', { exact: true }).check()
    await page.getByText('Advanced answer controls', { exact: true }).click()
    await page
      .getByLabel('Fields (optional JSON; skips automatic planning)')
      .fill(
        '{"amount":{"kind":"number","pointer":"/amount"},"zero":{"kind":"integer","pointer":"/zero"},"unknown":{"kind":"integer","nullable":true,"pointer":"/unknown"}}',
      )
    await page
      .getByLabel('Ask a question', { exact: true })
      .fill('What are the amount, zero and unknown values in precision-check?')
    await page
      .getByRole('button', { name: 'Ask question', exact: true })
      .click()
    await expect(page.locator('.fact strong').first()).toHaveText(
      '9007199254740993.00000000000001',
      { timeout: 120000 },
    )
    await expect(page.locator('.fact strong').nth(1)).toHaveText('null')
    await expect(page.locator('.fact strong').nth(2)).toHaveText('0')
    await page.reload()
    await expect(page.locator('.fact strong').first()).toHaveText(
      '9007199254740993.00000000000001',
    )
    await page
      .locator('article.document')
      .filter({ hasText: 'apollo11.pdf' })
      .getByRole('button', { name: 'Inspect', exact: true })
      .click()
    await expect(
      page.getByRole('link', { name: 'Open original PDF' }),
    ).toBeVisible()
    const href = await page
      .getByRole('link', { name: 'Open original PDF' })
      .getAttribute('href')
    expect(
      (await page.request.get('http://localhost:4180' + href)).status(),
    ).toBe(200)
    await mkdir('test-results', { recursive: true })
    await writeFile(
      'test-results/live-browser-responses.json',
      JSON.stringify(captured, null, 2),
    )
    expect(failures).toEqual([])
  })
})
