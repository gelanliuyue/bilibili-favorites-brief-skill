import MarkmapEditor from '@/pages/HomePage/components/MarkmapComponent'

interface BriefMindMapProps {
  markdown: string
  title: string
}

export function BriefMindMap({ markdown, title }: BriefMindMapProps) {
  return (
    <div className="brief-map" aria-label="视频知识思维导图">
      <MarkmapEditor
        value={markdown}
        onChange={() => undefined}
        height="520px"
        title={title}
      />
    </div>
  )
}
