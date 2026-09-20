/**
 * Standalone QA screenshot script — NOT part of the e2e suite.
 * Runs against a live stack (default http://localhost:3000) and saves
 * screenshots of a case into Prints/ for manual review.
 *
 * Usage: node tests/manual/qa-screenshots.js
 */
const { chromium } = require('playwright')
const path = require('node:path')
const fs = require('node:fs')

const BASE = process.env.SOKOL_WEB_URL || 'http://localhost:3000'
const OUT_DIR = path.resolve(__dirname, '../../../Prints')
const CASE_NAME = process.env.SOKOL_QA_CASE || 'CPX'

const TABS = [
  'Timeline',
  'Busca',
  'Chat',
  'Conversas',
  'Dados',
  'Bookmarks',
  'Watchlists',
  'Pendências',
  'Mídia',
  'Rostos',
  'Placas',
  'Voz',
  'OCR',
  'Analytics',
  'Grafo',
  'Playbooks',
  'Relatórios',
  'Análise Cruzada',
  'Identidades',
  'Operação',
]

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true })

  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })

  let n = 1
  const shot = async (name) => {
    const file = path.join(OUT_DIR, `${String(n).padStart(2, '0')}-${name}.png`)
    await page.screenshot({ path: file, fullPage: true })
    console.log('saved', file)
    n += 1
  }

  await page.goto(`${BASE}/login`)
  await shot('login')

  await page.getByLabel(/usuário|usuario/i).fill('admin')
  await page.getByLabel(/senha/i).fill('admin123')
  await page.getByRole('button', { name: /entrar/i }).click()
  await page.waitForURL(/\/cases/)
  await shot('cases-list')

  await page.getByRole('button', { name: new RegExp(CASE_NAME, 'i') }).first().click()
  await page.waitForURL(/\/cases\/[^/]+/)
  await page.waitForTimeout(1000)
  await shot('case-overview')

  for (const tab of TABS) {
    const btn = page.getByRole('button', { name: tab, exact: true })
    if ((await btn.count()) === 0) {
      console.log('skip (not found):', tab)
      continue
    }
    await btn.first().click()
    await page.waitForTimeout(5000)
    const slug = tab
      .toLowerCase()
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')
    await shot(`tab-${slug}`)
  }

  await browser.close()
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
