import { useQuery } from '@tanstack/react-query'
import { apiListOCR, type OCRResult } from '@/lib/api'
import { useState } from 'react'
import { FileText, Loader2, Camera } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn } from '@/lib/cn'

const INPUT_CLASS =
  'h-11 rounded-lg border border-border bg-surface-elevated px-4 text-sm text-foreground placeholder:text-dim transition-colors duration-150 hover:border-border-hover focus:border-border-hover focus:outline-none focus:ring-1 focus:ring-white/10 disabled:opacity-50'

function MediaThumbnail({ hash, caseId }: { hash: string; caseId: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) return <Camera className="h-8 w-8 text-dim" />
  return (
    <img
      src={`/api/media/file/${hash}?case_id=${caseId}`}
      alt="Documento"
      className="h-full w-full object-contain"
      loading="lazy"
      onError={() => setFailed(true)}
    />
  )
}

export function OCRTab({ caseId }: { caseId: string }) {
  const [search, setSearch] = useState('')

  const { data: results = [], isLoading } = useQuery({
    queryKey: ['ocr', caseId, search],
    queryFn: () => apiListOCR(caseId, search || undefined),
  })

  return (
    <>
      <PageHeader
        icon={FileText}
        title="OCR - Documentos"
        description={`${results.length} documento(s) com texto extraído`}
      />

      <div className="mb-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar no texto extraído por OCR..."
          className={cn('w-full', INPUT_CLASS)}
        />
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-5 w-5 animate-spin text-muted" />
        </div>
      ) : results.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="Nenhum documento com OCR"
          description="Execute o pipeline de detecção na aba Mídia para extrair texto de documentos e imagens."
        />
      ) : (
        <div className="space-y-4">
          {results.map((r) => (
            <Card key={r.id} className="overflow-hidden hover:border-border-hover">
              <div className="flex">
                <div className="hidden w-32 shrink-0 items-center justify-center bg-surface-elevated sm:flex">
                  <MediaThumbnail hash={r.media_hash} caseId={caseId} />
                </div>
                <CardContent className="flex-1 py-4">
                  <div className="mb-2 flex items-center gap-2">
                    <FileText className="h-3.5 w-3.5 text-dim" />
                    <span className="text-[10px] text-dim">
                      {new Date(r.created_at).toLocaleString('pt-BR')}
                    </span>
                    {r.language && (
                      <Badge className="text-[10px]">{r.language}</Badge>
                    )}
                    {r.confidence != null && (
                      <Badge variant="accent" className="text-[10px]">
                        {(r.confidence * 100).toFixed(0)}%
                      </Badge>
                    )}
                  </div>
                  <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-foreground">
                    {r.text}
                  </p>
                </CardContent>
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  )
}
