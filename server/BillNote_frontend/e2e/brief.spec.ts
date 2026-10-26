import { expect, test, type Page } from '@playwright/test'

const resultMarkdown = `# 视频标题

## 一句话结论
真正有用的不是收藏视频，而是把教程拆成可检索的知识卡。

## 是否值得看
评分：8.6/10
适合：准备建立知识库的人
不适合：寻找安装步骤的人

## 核心摘要
- 先判断视频是否值得投入时间。
- 再把章节和知识点整理成结构。

## 章节
- [00:12] 第一章节：开场说明。
- [01:05] 第二章节：关键方法。

## 术语
- 时间锚点：回到原视频指定秒数。

## 行动清单
1. 只看评分最高的章节。
`

async function installApiMocks(
  page: Page,
  options: {
    subtitleError?: boolean
    taskStatuses?: string[]
    biliLoggedIn?: boolean
  } = {},
) {
  let statusIndex = 0
  let qrPollIndex = 0
  const taskStatuses = options.taskStatuses ?? ['SUMMARIZING', 'SUCCESS']

  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    const json = (body: unknown) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(body),
      })

    if (url.pathname.endsWith('/sys_check')) {
      return json({ code: 0, msg: 'ok', data: { ready: true } })
    }
    if (url.pathname.endsWith('/sys_health')) {
      return json({
        code: 0,
        msg: 'ok',
        data: {
          backend: 'ok',
          ffmpeg: 'ok',
          db: 'ok',
          whisper_model: {
            size: 'tiny',
            type: 'fast-whisper',
            downloaded: false,
            checked: true,
          },
        },
      })
    }
    if (url.pathname.endsWith('/get_all_providers')) {
      return json({
        code: 0,
        msg: 'ok',
        data: [
          {
            id: 'deepseek',
            name: 'DeepSeek',
            base_url: 'https://api.deepseek.com',
            type: 'built-in',
            api_key: 'sk-t****0000',
            enabled: 1,
          },
          {
            id: 'qwen',
            name: 'Qwen',
            base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
            type: 'built-in',
            api_key: '',
            enabled: 1,
          },
        ],
      })
    }
    if (url.pathname.endsWith('/bilibili_auth/status')) {
      return json({
        code: 0,
        msg: 'ok',
        data: options.biliLoggedIn
          ? { logged_in: true, uname: '测试用户', face: '' }
          : { logged_in: false },
      })
    }
    if (url.pathname.endsWith('/bilibili_auth/qr/start')) {
      return json({
        code: 0,
        msg: 'ok',
        data: {
          session_id: 'qr-session',
          qr_url: 'https://www.bilibili.com/login-qr',
          expires_in: 180,
        },
      })
    }
    if (url.pathname.includes('/bilibili_auth/qr/poll/')) {
      qrPollIndex += 1
      if (qrPollIndex === 1) {
        return json({
          code: 0,
          msg: 'ok',
          data: {
            status: 'scanned',
            message: '已扫码，请在手机中确认',
          },
        })
      }
      return json({
        code: 0,
        msg: 'ok',
        data: {
          status: 'success',
          message: '登录成功',
          account: { logged_in: true, uname: '测试用户', face: '' },
        },
      })
    }
    if (url.pathname.endsWith('/bilibili_auth/import_browser')) {
      return json({
        code: 0,
        msg: 'ok',
        data: { logged_in: true, uname: '浏览器账号', face: '' },
      })
    }
    if (url.pathname.endsWith('/bilibili_auth/logout')) {
      return json({ code: 0, msg: 'ok', data: null })
    }
    if (url.pathname.endsWith('/asr/settings')) {
      const requestMethod = route.request().method()
      const mode =
        requestMethod === 'PUT'
          ? (JSON.parse(route.request().postData() ?? '{}').mode as string)
          : 'subtitle_only'
      return json({
        code: 0,
        msg: 'ok',
        data: {
          mode,
          available_modes: ['subtitle_only', 'bcut', 'kuaishou', 'groq'],
        },
      })
    }
    if (url.pathname.includes('/model_list/')) {
      return json({
        code: 0,
        msg: 'ok',
        data: [{ id: 1, provider_id: 'deepseek', model_name: 'deepseek-chat' }],
      })
    }
    if (url.pathname.endsWith('/update_provider')) {
      return json({ code: 0, msg: 'ok', data: { id: 'deepseek', enabled: 1 } })
    }
    if (url.pathname.endsWith('/connect_test')) {
      return json({ code: 0, msg: '连接成功', data: null })
    }
    if (url.pathname.endsWith('/update_downloader_cookie')) {
      return json({ code: 0, msg: 'ok', data: null })
    }
    if (url.pathname.endsWith('/generate_note')) {
      if (options.subtitleError) {
        return json({
          code: 300102,
          msg: '转写模型尚未下载就绪',
          data: {
            reason: 'transcriber_model_not_ready',
            subtitle_checked: true,
          },
        })
      }
      return json({ code: 0, msg: 'ok', data: { task_id: 'task-e2e' } })
    }
    if (url.pathname.includes('/task_status/')) {
      const status = taskStatuses[Math.min(statusIndex, taskStatuses.length - 1)]
      statusIndex += 1
      if (status === 'SUCCESS') {
        return json({
          code: 0,
          msg: 'ok',
          data: {
            status,
            task_id: 'task-e2e',
            result: {
              markdown: resultMarkdown,
              audio_meta: {
                title: '把视频教程变成知识卡',
                duration: 120,
                cover_url: '',
                platform: 'bilibili',
                video_id: 'BV1xx411c7mD',
              },
            },
          },
        })
      }
      return json({
        code: 0,
        msg: '处理中',
        data: { status, task_id: 'task-e2e', message: '正在提炼摘要与章节' },
      })
    }

    return json({ code: 0, msg: 'ok', data: null })
  })
}

test('setup saves a masked provider key', async ({ page }) => {
  await installApiMocks(page)
  await page.goto('/brief/setup', { waitUntil: 'domcontentloaded', timeout: 90_000 })

  await expect(page.getByRole('heading', { name: '连接你的模型和 B 站' })).toBeVisible()
  const saveButtonColors = await page
    .getByRole('button', { name: '保存模型配置' })
    .evaluate((node) => {
      const style = getComputedStyle(node)
      return { color: style.color, background: style.backgroundColor }
    })
  expect(saveButtonColors.color).not.toBe(saveButtonColors.background)
  await page.getByLabel('API Key', { exact: true }).fill('sk-test-placeholder-0000')
  await page.getByRole('button', { name: '保存模型配置' }).click()

  await expect(page.getByLabel('已保存的 API Key')).toContainText('已保存')
  await expect(page.getByText('sk-test-placeholder-0000')).toHaveCount(0)
})

test('valid link moves from processing to the result and mind map', async ({ page }) => {
  await installApiMocks(page)
  await page.goto('/brief', { waitUntil: 'domcontentloaded', timeout: 60_000 })

  await page.getByLabel('B 站视频链接').fill('BV1xx411c7mD')
  await page.getByRole('button', { name: '开始拆解' }).click()
  await expect(page.getByRole('heading', { name: '正在理解这个视频' })).toBeVisible()

  await expect(page.getByText('真正有用的不是收藏视频，而是把教程拆成可检索的知识卡。')).toBeVisible({
    timeout: 10_000,
  })
  await expect(page.getByRole('button', { name: '导出 Markdown' })).toBeVisible()

  await page.getByRole('tab', { name: '思维导图' }).click()
  await expect(page.getByRole('tab', { name: '思维导图' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
})

test('missing subtitles show actionable ASR guidance', async ({ page }) => {
  await installApiMocks(page, { subtitleError: true })
  await page.goto('/brief', { waitUntil: 'domcontentloaded', timeout: 60_000 })

  await page.getByLabel('B 站视频链接').fill('BV1xx411c7mD')
  await page.getByRole('button', { name: '开始拆解' }).click()

  await expect(page.getByRole('alert')).toContainText('没有可用字幕')
  await expect(page.getByRole('alert')).toContainText('语音识别')
  await expect(page.getByRole('button', { name: '去设置' })).toBeVisible()
})

test('setup generates a QR login and configures cloud ASR', async ({ page }) => {
  await installApiMocks(page)
  await page.goto('/brief/setup', { waitUntil: 'domcontentloaded', timeout: 90_000 })

  await page.getByRole('button', { name: '扫码登录 B 站' }).click()
  await expect(page.getByTestId('bilibili-login-qr')).toBeVisible()
  await expect(page.getByText('已扫码，请在手机中确认')).toBeVisible({
    timeout: 6_000,
  })
  await expect(page.getByText('已登录：测试用户')).toBeVisible({
    timeout: 6_000,
  })

  await page.getByRole('radio', { name: /必剪在线转写/ }).check()
  await expect(page.getByRole('radio', { name: /必剪在线转写/ })).toBeChecked()
})

test('browser cookie import is available as a fallback', async ({ page }) => {
  await installApiMocks(page)
  await page.goto('/brief/setup', { waitUntil: 'domcontentloaded', timeout: 90_000 })

  await page.getByRole('button', { name: '从 Edge 导入' }).click()
  await expect(page.getByText('已登录：浏览器账号')).toBeVisible()
  await expect(page.getByText(/SESSDATA/)).toHaveCount(0)
})

for (const viewport of [
  { width: 390, height: 844 },
  { width: 320, height: 700 },
]) {
  test(`home has no horizontal overflow at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await installApiMocks(page)
    await page.goto('/brief', { waitUntil: 'domcontentloaded', timeout: 60_000 })
    await expect(page.getByRole('heading', { name: '今天想拆解哪个教程？' })).toBeVisible()

    const overflow = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }))

    expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth)
  })
}
