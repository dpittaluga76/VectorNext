import { test, expect } from '@playwright/test'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

const url = process.env.VECTORNEXT_PLANNING_URL
const exact = '9007199254740995.00000000000009'

test('automatic count, follow-up and exact JSON survive browser history and export', async ({
  page,
}) => {
  test.skip(
    !url,
    'Requires the explicitly prepared isolated T26 fixture library',
  )
  test.setTimeout(600000)
  page.setDefaultTimeout(30000)
  const errors: string[] = []
  const requests: Record<string, unknown>[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('request', (r) => {
    if (r.url().endsWith('/v1/ui/ask')) requests.push(r.postDataJSON())
  })
  const replay = process.env.VECTORNEXT_PLANNING_REPLAY
  if (replay) {
    const captures = new Map<string, Buffer>()
    for (const name of readdirSync(replay).filter((n) =>
      n.endsWith('-request.json'),
    )) {
      const saved = JSON.parse(readFileSync(join(replay, name), 'utf8'))
      if (saved.path === '/v1/ui/ask') {
        captures.set(
          saved.request.question,
          readFileSync(
            join(replay, name.replace('-request.json', '-response.json')),
          ),
        )
      }
    }
    await page.route('**/v1/ui/ask', (route) => {
      const body = captures.get(route.request().postDataJSON().question)
      if (!body)
        throw new Error('No captured response for this browser question')
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body,
      })
    })
  }
  await page.goto(url!)
  await page.getByLabel('harbor.txt', { exact: true }).check()
  await page.getByText('Advanced answer controls', { exact: true }).click()
  await page.getByLabel('Evidence selection').selectOption('facet_coverage_v1')
  const ask = async (question: string, value: string) => {
    await page.getByLabel('Ask a question', { exact: true }).fill(question)
    await expect(
      page.getByRole('button', { name: 'Ask question', exact: true }),
    ).toBeEnabled({ timeout: 30000 })
    const reply = page.waitForResponse((r) => r.url().endsWith('/v1/ui/ask'), {
      timeout: 180000,
    })
    await page
      .getByRole('button', { name: 'Ask question', exact: true })
      .click()
    await test.info().attach(`answer-${requests.length}`, {
      body: await (await reply).body(),
      contentType: 'application/json',
    })
    await expect(page.getByText(value, { exact: true })).toBeVisible({
      timeout: 180000,
    })
  }
  await ask('How many probes does the Harbor expedition have?', '8')
  await ask('Who directs it?', 'Inez Flores')
  expect(requests).toHaveLength(2)
  expect(requests.every((r) => !('fields' in r))).toBe(true)
  expect(requests[1].history).toEqual([
    { role: 'user', text: 'How many probes does the Harbor expedition have?' },
    expect.objectContaining({
      role: 'assistant',
      text: expect.stringContaining('8'),
    }),
  ])
  await page.reload()
  await expect(page.getByText('Inez Flores', { exact: true })).toBeVisible()
  await page.getByLabel('harbor.txt', { exact: true }).uncheck()
  await page.getByLabel('precision.json', { exact: true }).check()
  await page.getByText('Advanced answer controls', { exact: true }).click()
  await page.getByLabel('Evidence selection').selectOption('facet_coverage_v1')
  await ask(
    'What are the numeric amount, integer zero and raw nullable integer unknown stored in precision-spruce?',
    exact,
  )
  await expect(page.getByText('0', { exact: true })).toBeVisible()
  await expect(
    page.locator('strong').filter({ hasText: /^null$/ }),
  ).toBeVisible()
  expect(requests[2].history).toEqual([])
  expect(requests[2]).not.toHaveProperty('fields')
  await page
    .getByRole('button', { name: /^Source E1 for / })
    .first()
    .click()
  await expect(page.locator('blockquote')).toContainText(exact)
  await page.getByText('How did you find this?', { exact: true }).click()
  const download = page.waitForEvent('download')
  await page
    .getByRole('button', { name: 'Export complete diagnostics' })
    .click()
  const saved = await download
  await saved.saveAs('/tmp/t26-browser-diagnostics.json')
  const stream = await saved.createReadStream()
  const parts = []
  for await (const part of stream!) parts.push(part)
  const raw = Buffer.concat(parts).toString()
  expect(raw).toContain(exact)
  expect(raw).toContain('field-planning-v3')
  await page.reload()
  await expect(page.getByText(exact, { exact: true })).toBeVisible()
  expect(errors).toEqual([])
  await page.screenshot({ path: '/tmp/t26-browser.png', fullPage: true })
})
