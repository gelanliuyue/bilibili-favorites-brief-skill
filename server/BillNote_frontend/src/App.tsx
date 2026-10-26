import './App.css'
import { Suspense, useEffect } from 'react'
import { BrowserRouter, HashRouter } from 'react-router-dom'
import { useTaskPolling } from '@/hooks/useTaskPolling.ts'
import { useCheckBackend } from '@/hooks/useCheckBackend.ts'
import { systemCheck } from '@/services/system.ts'
import BackendInitDialog from '@/components/BackendInitDialog'
import StartupBanner from '@/components/SystemDiagnostic/StartupBanner'
import BackendHealthIndicator from '@/components/BackendHealth/BackendHealthIndicator'
import { BriefRoutes } from '@/brief/routes'

function App() {
  useTaskPolling(3000) // 每 3 秒轮询一次
  const { loading, initialized, failed, lastError, retry } = useCheckBackend()

  // 在后端初始化完成后执行系统检查
  useEffect(() => {
    if (initialized) {
      systemCheck()
    }
  }, [initialized])

  // 如果后端还未初始化，显示初始化对话框（loading 或 failed 都展示，由 dialog 内部决定渲染哪一态）
  if (!initialized) {
    return (
      <>
        <StartupBanner />
        <BackendInitDialog
          open={loading}
          failed={failed}
          lastError={lastError}
          onRetry={retry}
        />
      </>
    )
  }

  // 桌面端使用 HashRouter 避免刷新 404；Web 端继续使用 BrowserRouter
  const isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window
  const Router = isTauri ? HashRouter : BrowserRouter

  // 后端已初始化，渲染主应用
  return (
    <>
      <StartupBanner />
      <BackendHealthIndicator />
      <Router>
        <Suspense fallback={<div className="flex h-screen items-center justify-center">加载中…</div>}>
          <BriefRoutes />
        </Suspense>
      </Router>
    </>
  )
}

export default App
