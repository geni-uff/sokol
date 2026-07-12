import { test, expect } from '@playwright/test'

test.describe('Cases Management', () => {
  test.beforeEach(async ({ page }) => {
    // Login first
    await page.goto('http://localhost:5175/login')
    await page.getByLabel(/email|username/i).fill('admin')
    await page.getByLabel(/password/i).fill('admin123')
    await page.getByRole('button', { name: /login|entrar/i }).click()
    await page.waitForURL(/\/cases/)
  })

  test('should list cases', async ({ page }) => {
    // Should see cases page
    await expect(page.getByText(/casos|cases/i)).toBeVisible()

    // Should show at least one case card
    const caseCards = page.getByRole('button').filter({ hasText: /caso|case/i })
    expect(await caseCards.count()).toBeGreaterThan(0)
  })

  test('should open case detail', async ({ page }) => {
    // Click first case
    const firstCase = page.locator('[role="button"]').filter({ hasText: /caso|case/i }).first()
    await firstCase.click()

    // Should navigate to case detail
    await expect(page).toHaveURL(/\/cases\/[a-f0-9-]+/)

    // Should show tabs
    await expect(page.getByRole('button', { name: /Timeline|Busca|Chat/i })).toBeTruthy()
  })

  test('should navigate through tabs', async ({ page }) => {
    // Open first case
    const firstCase = page.locator('[role="button"]').filter({ hasText: /caso|case/i }).first()
    await firstCase.click()
    await expect(page).toHaveURL(/\/cases\/[a-f0-9-]+/)

    // Click Busca tab
    await page.getByRole('button', { name: /Busca/ }).click()
    await expect(page.getByPlaceholder(/search|buscar|pesquisar/i)).toBeVisible()

    // Click Chat tab
    await page.getByRole('button', { name: /Chat/ }).click()
    await expect(page.getByPlaceholder(/mensagem|message/i)).toBeVisible()
  })

  test('should view reports tab', async ({ page }) => {
    // Open first case
    const firstCase = page.locator('[role="button"]').filter({ hasText: /caso|case/i }).first()
    await firstCase.click()
    await expect(page).toHaveURL(/\/cases\/[a-f0-9-]+/)

    // Click Reports tab
    await page.getByRole('button', { name: /Relatórios|Reports/ }).click()

    // Should show generate button
    await expect(page.getByRole('button', { name: /Gerar|Generate/ })).toBeVisible()
  })
})
