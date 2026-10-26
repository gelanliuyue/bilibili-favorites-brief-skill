import { lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { HomePage } from '@/pages/HomePage/Home.tsx'
import { BriefWorkspace } from './BriefWorkspace'

const Onboarding = lazy(() => import('@/pages/Onboarding'))
const SettingPage = lazy(() => import('@/pages/SettingPage/index.tsx'))
const Model = lazy(() => import('@/pages/SettingPage/Model.tsx'))
const ProviderForm = lazy(() => import('@/components/Form/modelForm/Form.tsx'))
const AboutPage = lazy(() => import('@/pages/SettingPage/about.tsx'))
const Monitor = lazy(() => import('@/pages/SettingPage/Monitor.tsx'))
const Downloader = lazy(() => import('@/pages/SettingPage/Downloader.tsx'))
const DownloaderForm = lazy(() => import('@/components/Form/DownloaderForm/Form.tsx'))
const TranscriberPage = lazy(() => import('@/pages/SettingPage/transcriber.tsx'))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'))

export function BriefRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/brief" replace />} />
      <Route path="/brief" element={<BriefWorkspace view="home" />} />
      <Route path="/brief/setup" element={<BriefWorkspace view="setup" />} />
      <Route path="/brief/library" element={<BriefWorkspace view="library" />} />
      <Route path="/brief/task/:taskId" element={<BriefWorkspace view="task" />} />
      <Route path="/classic" element={<HomePage />} />

      <Route path="/onboarding" element={<Onboarding />} />
      <Route path="/settings" element={<SettingPage />}>
        <Route index element={<Navigate to="model" replace />} />
        <Route path="model" element={<Model />}>
          <Route path="new" element={<ProviderForm isCreate />} />
          <Route path=":id" element={<ProviderForm />} />
        </Route>
        <Route path="download" element={<Downloader />}>
          <Route path=":id" element={<DownloaderForm />} />
        </Route>
        <Route path="transcriber" element={<TranscriberPage />} />
        <Route path="monitor" element={<Monitor />} />
        <Route path="about" element={<AboutPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
