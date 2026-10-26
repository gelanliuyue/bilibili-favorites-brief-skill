import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useStore } from 'zustand'
import { LoaderCircle } from 'lucide-react'
import { BriefHome } from './components/BriefHome'
import { BriefLibrary } from './components/BriefLibrary'
import { BriefProcessing } from './components/BriefProcessing'
import { BriefResult } from './components/BriefResult'
import { BriefSetup } from './components/BriefSetup'
import {
  BriefShell,
  type BriefDestination,
} from './components/BriefShell'
import { useBriefPolling } from './hooks/useBriefPolling'
import { parseBriefMarkdown } from './lib/parseBriefMarkdown'
import { describeTaskPresentation } from './lib/taskPresentation'
import {
  getAsrSettings,
  getBilibiliStatus,
  getBriefTask,
  listModels,
  listProviders,
  saveBilibiliCookie,
  submitBrief,
  testProvider,
  updateAsrMode,
  updateProvider,
} from './services/briefApi'
import { briefStore } from './store/briefStore'
import type {
  AsrMode,
  BilibiliAccount,
  BriefModel,
  BriefProvider,
  BriefTask,
  BriefTaskResult,
} from './types'

type BriefView = 'home' | 'setup' | 'library' | 'task'

interface BriefWorkspaceProps {
  view: BriefView
}

const fallbackProviders: BriefProvider[] = [
  {
    id: 'deepseek',
    name: 'DeepSeek',
    base_url: 'https://api.deepseek.com',
    type: 'built-in',
  },
  {
    id: 'qwen',
    name: 'Qwen',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    type: 'built-in',
  },
]

function defaultModelName(providerId: string): string {
  return providerId === 'qwen' ? 'qwen-plus' : 'deepseek-chat'
}

function selectableProvider(provider: BriefProvider): boolean {
  const id = provider.id.toLowerCase()
  const name = provider.name.toLowerCase()
  return id === 'deepseek' || id === 'qwen' || name.includes('deepseek') || name.includes('qwen')
}

function taskIsActive(status: BriefTask['status']): boolean {
  return !['SUCCESS', 'FAILED'].includes(status)
}

function downloadMarkdown(task: BriefTask) {
  if (!task.markdown) return
  const blob = new Blob([task.markdown], {
    type: 'text/markdown;charset=utf-8',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${task.audioMeta?.title || 'BiliBrief'}.md`
  link.click()
  URL.revokeObjectURL(url)
}

function TaskWorkspace({
  taskId,
  onBack,
  onRetry,
}: {
  taskId: string
  onBack: () => void
  onRetry: (task: BriefTask) => void
}) {
  const tasks = useStore(briefStore, (state) => state.tasks)
  const hydrated = useStore(briefStore, (state) => state.hydrated)
  const applyTaskStatus = useStore(briefStore, (state) => state.applyTaskStatus)
  const task = tasks.find((item) => item.id === taskId)

  const applyResult = (result: BriefTaskResult) => {
    if (!task) return
    const markdown = result.result?.markdown
    applyTaskStatus(task.id, {
      status: result.status,
      message: result.message,
      markdown,
      document: markdown ? parseBriefMarkdown(markdown) : task.document,
      audioMeta: result.result?.audio_meta ?? task.audioMeta,
    })
  }

  useBriefPolling({
    taskId: task?.id ?? null,
    active: Boolean(task && taskIsActive(task.status)),
    getStatus: getBriefTask,
    onUpdate: applyResult,
    onError: (error) => {
      if (!task) return
      const message =
        (error as { message?: string })?.message || '任务状态读取失败，正在重试。'
      applyTaskStatus(task.id, { status: task.status, message })
    },
  })

  const presentation = describeTaskPresentation(task, hydrated)

  if (presentation === 'hydrating') {
    return (
      <section className="brief-processing" aria-live="polite">
        <span className="brief-processing__icon">
          <LoaderCircle size={25} className="brief-spin" aria-hidden="true" />
        </span>
        <h1>正在打开任务</h1>
        <p>正在读取本机保存的资料。</p>
      </section>
    )
  }

  if (presentation === 'missing' || !task) {
    return (
      <section className="brief-processing brief-processing--failed" role="alert">
        <h1>找不到这个任务</h1>
        <p>任务可能已被删除，或者本机浏览器没有保存它的历史。</p>
        <button className="brief-button" type="button" onClick={onBack}>
          返回首页
        </button>
      </section>
    )
  }

  if (presentation === 'result' && task.document && task.markdown) {
    return (
      <BriefResult
        title={task.audioMeta?.title || '视频知识卡'}
        videoUrl={task.videoUrl}
        document={task.document}
        onBack={onBack}
        onExportMarkdown={() => downloadMarkdown(task)}
      />
    )
  }

  if (presentation === 'incomplete') {
    return (
      <BriefProcessing
        status="FAILED"
        message="摘要任务显示成功，但没有保存完整结果。请重新处理这个视频。"
        onRetry={() => onRetry(task)}
      />
    )
  }

  return (
    <BriefProcessing
      status={task.status}
      message={task.message}
      onRetry={task.status === 'FAILED' ? () => onRetry(task) : undefined}
    />
  )
}

export function BriefWorkspace({ view }: BriefWorkspaceProps) {
  const navigate = useNavigate()
  const { taskId } = useParams()
  const tasks = useStore(briefStore, (state) => state.tasks)
  const addTask = useStore(briefStore, (state) => state.addTask)
  const applyTaskStatus = useStore(briefStore, (state) => state.applyTaskStatus)
  const [providers, setProviders] = useState<BriefProvider[]>(fallbackProviders)
  const [providerId, setProviderId] = useState(
    () => localStorage.getItem('bili-brief-provider') || 'deepseek',
  )
  const [models, setModels] = useState<BriefModel[]>([])
  const [modelName, setModelName] = useState(
    () => localStorage.getItem('bili-brief-model') || '',
  )
  const [bilibiliAccount, setBilibiliAccount] = useState<BilibiliAccount>({
    logged_in: false,
  })
  const [asrMode, setAsrMode] = useState<AsrMode>('subtitle_only')
  const [loadMessage, setLoadMessage] = useState('')

  const refreshProviders = async () => {
    try {
      const remoteProviders = await listProviders()
      const supported = remoteProviders.filter(selectableProvider)
      setProviders(supported.length ? supported : fallbackProviders)
    } catch {
      setLoadMessage('暂时无法读取后端模型配置，已显示默认供应商。')
    }
  }

  useEffect(() => {
    void refreshProviders()
  }, [])

  useEffect(() => {
    void getBilibiliStatus()
      .then(setBilibiliAccount)
      .catch(() => undefined)
    void getAsrSettings()
      .then((settings) => setAsrMode(settings.mode))
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    let ignored = false
    const load = async () => {
      try {
        const remoteModels = await listModels(providerId)
        if (ignored) return
        const nextModels = remoteModels.length
          ? remoteModels
          : [{ model_name: defaultModelName(providerId) }]
        setModels(nextModels)
        setModelName((current) =>
          nextModels.some((model) => model.model_name === current)
            ? current
            : nextModels[0].model_name,
        )
      } catch {
        if (ignored) return
        const fallback = [{ model_name: defaultModelName(providerId) }]
        setModels(fallback)
        setModelName(fallback[0].model_name)
      }
    }
    void load()
    return () => {
      ignored = true
    }
  }, [providerId])

  useEffect(() => {
    if (modelName) localStorage.setItem('bili-brief-model', modelName)
  }, [modelName])

  const provider = providers.find((item) => item.id === providerId)
  const model = models.find((item) => item.model_name === modelName) ?? models[0]
  const currentDestination: BriefDestination =
    view === 'library' ? 'library' : view === 'setup' ? 'settings' : 'home'

  const navigateHome = () => navigate('/brief')
  const navigateSettings = () => navigate('/brief/setup')

  const saveKey = async ({
    providerId: nextProviderId,
    apiKey,
  }: {
    providerId: string
    apiKey: string
  }) => {
    await updateProvider({ id: nextProviderId, api_key: apiKey, enabled: 1 })
    setProviderId(nextProviderId)
    localStorage.setItem('bili-brief-provider', nextProviderId)
    await refreshProviders()
  }

  const saveCookie = async (cookie: string) => {
    await saveBilibiliCookie(cookie)
    try {
      setBilibiliAccount(await getBilibiliStatus())
    } catch {
      setBilibiliAccount({ logged_in: true })
    }
  }

  const submit = async ({
    videoUrl,
    providerId: nextProviderId,
    modelName: nextModelName,
  }: {
    videoUrl: string
    providerId: string
    modelName: string
  }) => {
    const response = await submitBrief({
      videoUrl,
      providerId: nextProviderId,
      modelName: nextModelName,
    })
    const now = new Date().toISOString()
    addTask({
      id: response.task_id,
      videoUrl,
      platform: 'bilibili',
      status: 'PENDING',
      message: '任务已提交，等待处理',
      createdAt: now,
      updatedAt: now,
      formData: {
        modelName: nextModelName,
        providerId: nextProviderId,
        quality: 'medium',
        style: 'brief',
      },
    })
    navigate(`/brief/task/${response.task_id}`)
    return response
  }

  const retry = async (task: BriefTask) => {
    applyTaskStatus(task.id, {
      status: 'PENDING',
      message: '正在重新提交任务',
    })
    try {
      await submitBrief({
        videoUrl: task.videoUrl,
        providerId: task.formData.providerId,
        modelName: task.formData.modelName,
        taskId: task.id,
      })
    } catch (error) {
      applyTaskStatus(task.id, {
        status: 'FAILED',
        message:
          (error as { message?: string })?.message || '重新提交失败，请稍后重试。',
      })
    }
  }

  const savedKeyHint = useMemo(() => {
    if (!provider?.api_key || provider.api_key.length < 4) return undefined
    return `已保存 ·${provider.api_key.slice(-6)}`
  }, [provider?.api_key])

  return (
    <BriefShell
      active={currentDestination}
      loggedIn={bilibiliAccount.logged_in}
      onNavigate={(destination) => {
        if (destination === 'home') navigate('/brief')
        if (destination === 'library') navigate('/brief/library')
        if (destination === 'settings') navigate('/brief/setup')
      }}
    >
      {loadMessage ? <p className="brief-note">{loadMessage}</p> : null}

      {view === 'home' ? (
        <BriefHome
          provider={provider}
          model={model}
          recentTasks={tasks}
          onSubmit={submit}
          onOpenSettings={navigateSettings}
          onOpenTask={(id) => navigate(`/brief/task/${id}`)}
        />
      ) : null}

      {view === 'setup' ? (
        <BriefSetup
          providers={providers}
          initialProviderId={providerId}
          savedKeyHint={savedKeyHint}
          cookieConfigured={bilibiliAccount.logged_in}
          bilibiliAccount={bilibiliAccount}
          asrMode={asrMode}
          onSaveKey={async (payload) => {
            setProviderId(payload.providerId)
            localStorage.setItem('bili-brief-provider', payload.providerId)
            await saveKey(payload)
          }}
          onTestConnection={async ({ providerId: nextProviderId }) => {
            await testProvider(nextProviderId, modelName)
          }}
          onSaveCookie={saveCookie}
          onBilibiliAccountChange={setBilibiliAccount}
          onAsrModeChange={async (nextMode) => {
            const previous = asrMode
            setAsrMode(nextMode)
            try {
              await updateAsrMode(nextMode)
            } catch {
              setAsrMode(previous)
            }
          }}
        />
      ) : null}

      {view === 'library' ? (
        <BriefLibrary
          tasks={tasks}
          onOpenTask={(id) => navigate(`/brief/task/${id}`)}
        />
      ) : null}

      {view === 'task' && taskId ? (
        <TaskWorkspace taskId={taskId} onBack={navigateHome} onRetry={retry} />
      ) : null}
    </BriefShell>
  )
}
