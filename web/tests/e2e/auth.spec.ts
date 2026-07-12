import { test, expect } from '@playwright/test'

test.describe('Authentication', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5175/login')
  })

  test('should show login form', async ({ page }) => {
    await expect(page.getByText('SOKOL')).toBeVisible()
    await expect(page.getByLabel(/email|username/i)).toBeVisible()
    await expect(page.getByLabel(/password/i)).toBeVisible()
  })

  test('should reject invalid credentials', async ({ page }) => {
    await page.getByLabel(/email|username/i).fill('invalid@test.com')
    await page.getByLabel(/password/i).fill('wrongpass')
    await page.getByRole('button', { name: /login|entrar/i }).click()

    await expect(page.getByText(/invalid|error|incorrect/i)).toBeVisible()
  })

  test('should login with valid credentials', async ({ page }) => {
    // Default credentials from setup
    await page.getByLabel(/email|username/i).fill('admin')
    await page.getByLabel(/password/i).fill('admin123')
    await page.getByRole('button', { name: /login|entrar/i }).click()

    // Should navigate to cases page
    await expect(page).toHaveURL(/\/cases/)
    await expect(page.getByText(/casos|cases/i)).toBeVisible()
  })

  test('should persist session token', async ({ page, context }) => {
    // Login
    await page.getByLabel(/email|username/i).fill('admin')
    await page.getByLabel(/password/i).fill('admin123')
    await page.getByRole('button', { name: /login|entrar/i }).click()

    // Check localStorage
    const token = await page.evaluate(() => localStorage.getItem('token'))
    expect(token).toBeTruthy()

    // Reload and should stay logged in
    await page.reload()
    await expect(page).toHaveURL(/\/cases/)
  })
})
