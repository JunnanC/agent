import { defineConfig, devices } from '@playwright/test'

const browserChannel = process.env.PLAYWRIGHT_CHANNEL as 'chrome' | 'msedge' | undefined

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  use: {
    trace: 'retain-on-failure',
    ...devices['Desktop Chrome'],
    channel: browserChannel,
    launchOptions: { args: ['--no-proxy-server'] },
  },
  projects: [
    { name: 'user-web', use: { baseURL: process.env.USER_WEB_URL ?? 'http://user.localhost:8080' }, grep: /@user/ },
    { name: 'teacher-web', use: { baseURL: process.env.TEACHER_WEB_URL ?? 'http://teacher.localhost:8080' }, grep: /@teacher/ },
    { name: 'admin-web', use: { baseURL: process.env.ADMIN_WEB_URL ?? 'http://admin.localhost:8080' }, grep: /@admin/ },
  ],
})
