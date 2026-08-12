import { test, expect } from '@playwright/test'

test.describe('Cases Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel(/email|username/i).fill('admin')
    await page.getByLabel(/password/i).fill('admin123')
    await page.getByRole('button', { name: /login|entrar/i }).click()
    await page.waitForURL(/\/cases/)
  })

  test('should list cases', async ({ page }) => {
    await expect(page.getByText(/casos|cases/i)).toBeVisible()
  })

  test('should create a case', async ({ page }) => {
    const name = `E2E Case ${Date.now()}`
    await page.getByRole('button', { name: /novo caso/i }).click()
    await page.getByLabel(/^Nome$/i).fill(name)
    await page.getByRole('button', { name: /criar caso/i }).click()
    await expect(page).toHaveURL(/\/cases\/[a-f0-9-]+/, { timeout: 15000 })
  })

  test('should open case detail', async ({ page }) => {
    const firstCase = page.locator('a[href*="/cases/"], [data-case-id]').first()
    if (await firstCase.count()) {
      await firstCase.click()
    } else {
      await page.getByText(/caso|case|e2e|test/i).first().click()
    }
    await expect(page).toHaveURL(/\/cases\/[a-f0-9-]+/)
  })

  test('should view reports tab with bulk export', async ({ page }) => {
    await page.goto('/cases')
    await page.waitForURL(/\/cases/)
    const link = page.locator('a[href*="/cases/"]').first()
    if (await link.count()) {
      await link.click()
    } else {
      await page.getByText(/caso|case|e2e|test/i).first().click()
    }
    await expect(page).toHaveURL(/\/cases\/[a-f0-9-]+/)
    await page.getByRole('button', { name: /Relatórios|Reports/ }).click()
    await expect(page.getByRole('button', { name: /Gerar|Generate/ })).toBeVisible()
    await expect(page.getByText(/Export em massa/i)).toBeVisible()
  })
})
