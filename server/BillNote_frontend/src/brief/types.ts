import type { BriefDocument } from './lib/parseBriefMarkdown'

export type BriefTaskStatus =
  | 'PENDING'
  | 'PARSING'
  | 'DOWNLOADING'
  | 'TRANSCRIBING'
  | 'SUMMARIZING'
  | 'FORMATTING'
  | 'SAVING'
  | 'SUCCESS'
  | 'FAILED'

export interface BriefFormData {
  modelName: string
  providerId: string
  quality: 'fast' | 'medium' | 'slow'
  style: 'brief'
}

export interface BriefAudioMeta {
  title: string
  duration: number
  cover_url: string
  platform: string
  video_id: string
  [key: string]: unknown
}

export interface BriefTask {
  id: string
  videoUrl: string
  platform: 'bilibili'
  status: BriefTaskStatus
  message: string
  createdAt: string
  updatedAt: string
  formData: BriefFormData
  markdown?: string
  document?: BriefDocument
  audioMeta?: BriefAudioMeta
}

export interface BriefTaskStatusUpdate {
  status: BriefTaskStatus
  message?: string
  markdown?: string
  document?: BriefDocument
  audioMeta?: BriefAudioMeta
}

export interface BriefProvider {
  id: string
  name: string
  base_url: string
  type: string
  logo?: string
  api_key?: string
  enabled?: number
}

export interface BriefModel {
  id?: number
  model_name: string
  provider_id?: string
}

export interface BriefTaskResult {
  status: BriefTaskStatus
  task_id: string
  message?: string
  result?: {
    markdown: string
    transcript?: unknown
    audio_meta?: BriefAudioMeta
  }
}

export const ACTIVE_TASK_STATUSES = new Set<BriefTaskStatus>([
  'PENDING',
  'PARSING',
  'DOWNLOADING',
  'TRANSCRIBING',
  'SUMMARIZING',
  'FORMATTING',
  'SAVING',
])

export interface BilibiliAccount {
  logged_in: boolean
  uname?: string
  face?: string
}

export interface BilibiliQrStart {
  session_id: string
  qr_url: string
  expires_in: number
}

export type BilibiliQrStatus =
  | 'waiting'
  | 'scanned'
  | 'expired'
  | 'success'
  | 'error'

export interface BilibiliQrPoll {
  status: BilibiliQrStatus
  message: string
  account?: BilibiliAccount
}

export type AsrMode = 'subtitle_only' | 'bcut' | 'kuaishou' | 'groq'

export interface AsrSettings {
  mode: AsrMode
  available_modes: AsrMode[]
}
