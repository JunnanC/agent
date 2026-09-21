import { expect, test } from '@playwright/test'

test('@user user portal shell and health', async ({ page }) => {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 920, height: 900 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport)
    await page.goto('/health')
    await expect(page.getByRole('heading', { name: '用户端' })).toBeVisible()
    await expect(page.getByText('服务正常')).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  }
  expect(await page.evaluate(() => localStorage.length)).toBe(0)
})

test('@teacher teacher portal shell and health', async ({ page }) => {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 920, height: 900 }]) {
    await page.setViewportSize(viewport)
    await page.goto('/health')
    await expect(page.getByRole('heading', { name: '教师端' })).toBeVisible()
    await expect(page.getByText('服务正常')).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  }
  expect(await page.evaluate(() => localStorage.length)).toBe(0)
})

test('@admin admin portal shell and health', async ({ page }) => {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 920, height: 900 }]) {
    await page.setViewportSize(viewport)
    await page.goto('/health')
    await expect(page.getByRole('heading', { name: '管理端' })).toBeVisible()
    await expect(page.getByText('服务正常')).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  }
  expect(await page.evaluate(() => localStorage.length)).toBe(0)
})
