import { beforeEach, describe, expect, it, vi } from 'vitest'
import request from '@/utils/request'
import {
  getBriefTask,
  importBilibiliBrowser,
  startBilibiliQr,
  submitBrief,
  updateAsrMode,
} from './briefApi'

vi.mock('@/utils/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}))

describe('briefApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('submits the fixed brief workflow payload', async () => {
    vi.mocked(request.post).mockResolvedValue({ task_id: 'task-1' })

    await submitBrief({
      videoUrl: 'https://www.bilibili.com/video/BV1xx411c7mD',
      providerId: 'deepseek',
      modelName: 'deepseek-chat',
    })

    expect(request.post).toHaveBeenCalledWith('/generate_note', {
      video_url: 'https://www.bilibili.com/video/BV1xx411c7mD',
      provider_id: 'deepseek',
      model_name: 'deepseek-chat',
      task_id: undefined,
      platform: 'bilibili',
      quality: 'medium',
      format: ['link', 'summary'],
      style: 'brief',
      screenshot: false,
      video_understanding: false,
      video_interval: 0,
      grid_size: [],
    })
  })

  it('turns a backend task failure into a terminal polling result', async () => {
    vi.mocked(request.get).mockRejectedValue({
      code: 500,
      msg: '视频没有可用字幕',
      data: { reason: 'transcriber_model_not_ready' },
    })

    await expect(getBriefTask('task-1')).resolves.toEqual({
      status: 'FAILED',
      task_id: 'task-1',
      message: '视频没有可用字幕',
    })
  })

  it('uses the QR and browser-import auth endpoints without a Cookie body', async () => {
    vi.mocked(request.post).mockResolvedValueOnce({
      session_id: 'session-1',
      qr_url: 'https://www.bilibili.com/login-qr',
      expires_in: 180,
    })
    vi.mocked(request.post).mockResolvedValueOnce({
      logged_in: true,
      uname: '测试用户',
    })

    await startBilibiliQr()
    await importBilibiliBrowser('edge')

    expect(request.post).toHaveBeenNthCalledWith(1, '/bilibili_auth/qr/start')
    expect(request.post).toHaveBeenNthCalledWith(
      2,
      '/bilibili_auth/import_browser',
      { browser: 'edge' },
    )
    expect(JSON.stringify(vi.mocked(request.post).mock.calls)).not.toContain(
      'SESSDATA',
    )
  })

  it('sends ASR mode changes to the dedicated endpoint', async () => {
    vi.mocked(request.put).mockResolvedValue({
      mode: 'bcut',
      available_modes: ['subtitle_only', 'bcut', 'kuaishou', 'groq'],
    })

    await updateAsrMode('bcut')

    expect(request.put).toHaveBeenCalledWith('/asr/settings', { mode: 'bcut' })
  })
})
