import { test, expect } from '@playwright/test'

const url = process.env.VECTORNEXT_FACET_URL
test('facet mode uses local models and retains captured workflow after reload', async ({
  page,
}) => {
  test.skip(
    !url,
    'Requires the explicitly prepared isolated T25 fixture library',
  )
  test.setTimeout(240000)
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.goto(url!)
  await page.getByLabel('aster.txt', { exact: true }).check()
  await page.getByText('Advanced answer controls', { exact: true }).click()
  await page.getByLabel('Evidence selection').selectOption('facet_coverage_v1')
  await page
    .getByLabel('Ask a question', { exact: true })
    .fill('In which year did the Aster station open?')
  await expect(
    page.getByRole('button', { name: 'Ask question', exact: true }),
  ).toBeEnabled({ timeout: 30000 })
  await page.getByRole('button', { name: 'Ask question', exact: true }).click()
  await expect(page.getByText('2017', { exact: true })).toBeVisible({
    timeout: 180000,
  })
  await page.getByText('How did you find this?', { exact: true }).click()
  await expect(
    page.locator('p').filter({ hasText: /^Facet coverage:/ }),
  ).toBeVisible()
  await expect(page.getByLabel('Recorded facet queries')).not.toBeEmpty()
  await page.getByRole('button', { name: 'Inspect [E1]', exact: true }).click()
  await expect(page.locator('blockquote')).toContainText('2017')
  const download = page.waitForEvent('download')
  await page
    .getByRole('button', { name: 'Export complete diagnostics' })
    .click()
  await (await download).saveAs('/tmp/t25-browser-diagnostics.json')
  await page.reload()
  await expect(page.getByText('2017', { exact: true })).toBeVisible()
  await page.getByText('How did you find this?', { exact: true }).click()
  await expect(
    page.locator('p').filter({ hasText: /^Facet coverage:/ }),
  ).toBeVisible()
  expect(errors).toEqual([])
  await page.screenshot({ path: '/tmp/t25-browser.png', fullPage: true })
})
