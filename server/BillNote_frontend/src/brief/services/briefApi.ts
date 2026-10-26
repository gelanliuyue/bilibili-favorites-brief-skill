import request from '@/utils/request'
import type {
  AsrMode,
  AsrSettings,
  BilibiliAccount,
  BilibiliQrPoll,
  BilibiliQrStart,
  BriefModel,
  BriefProvider,
  BriefTaskResult,
} from '../types'

export interface SubmitBriefInput {
  videoUrl: string
  providerId: string
  modelName: string
  taskId?: string
}

export async function listProviders(): Promise<BriefProvider[]> {
  return request.get('/get_all_providers') as Promise<BriefProvider[]>
}

export async function updateProvider(data: {
  id: string
  api_key?: string
  base_url?: string
  enabled?: number
}) {
  return request.post('/update_provider', data) as Promise<BriefProvider>
}

export async function listModels(providerId: string): Promise<BriefModel[]> {
  const models = (await request.get(
    `/model_list/${providerId}`,
  )) as BriefModel[]
  return models.filter((model) => Boolean(model.model_name))
}

export async function testProvider(providerId: string, model?: string) {
  return request.post('/connect_test', { id: providerId, model })
}

export async function saveBilibiliCookie(cookie: string) {
  return request.post('/update_downloader_cookie', {
    platform: 'bilibili',
    cookie: cookie.trim(),
  })
}

export async function submitBrief(
  input: SubmitBriefInput,
): Promise<{ task_id: string }> {
  return request.post('/generate_note', {
    video_url: input.videoUrl,
    provider_id: input.providerId,
    model_name: input.modelName,
    task_id: input.taskId,
    platform: 'bilibili',
    quality: 'medium',
    format: ['link', 'summary'],
    style: 'brief',
    screenshot: false,
    video_understanding: false,
    video_interval: 0,
    grid_size: [],
  }) as Promise<{ task_id: string }>
}

export async function getBriefTask(taskId: string): Promise<BriefTaskResult> {
  try {
    return (await request.get(
      `/task_status/${taskId}`,
    )) as BriefTaskResult
  } catch (error) {
    const payload = error as {
      code?: number
      msg?: string
    }
    if (payload && payload.msg) {
      return {
        status: 'FAILED',
        task_id: taskId,
        message: payload.msg,
      }
    }
    throw error
  }
}

export async function startBilibiliQr(): Promise<BilibiliQrStart> {
  return request.post('/bilibili_auth/qr/start') as Promise<BilibiliQrStart>
}

export async function pollBilibiliQr(
  sessionId: string,
): Promise<BilibiliQrPoll> {
  return request.get(
    `/bilibili_auth/qr/poll/${sessionId}`,
  ) as Promise<BilibiliQrPoll>
}

export async function getBilibiliStatus(): Promise<BilibiliAccount> {
  return request.get('/bilibili_auth/status') as Promise<BilibiliAccount>
}

export async function importBilibiliBrowser(
  browser: 'edge' | 'chrome',
): Promise<BilibiliAccount> {
  return request.post('/bilibili_auth/import_browser', {
    browser,
  }) as Promise<BilibiliAccount>
}

export async function logoutBilibili(): Promise<void> {
  await request.post('/bilibili_auth/logout')
}

export async function getAsrSettings(): Promise<AsrSettings> {
  return request.get('/asr/settings') as Promise<AsrSettings>
}

export async function updateAsrMode(mode: AsrMode): Promise<AsrSettings> {
  return request.put('/asr/settings', { mode }) as Promise<AsrSettings>
}
