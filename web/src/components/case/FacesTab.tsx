import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  apiListSubjects,
  apiListFaces,
  apiDetectFaces,
  apiSearchFaces,
  apiLabelFace,
  type FaceEmbedding,
  type FaceSearchResult,
  type FaceSubject,
} from '@/lib/api'
import { useState } from 'react'
import { User, Search, Loader2, X, ChevronDown, ChevronUp } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn } from '@/lib/cn'

const INPUT_CLASS =
  'h-11 rounded-lg border border-border bg-surface-elevated px-4 text-sm text-foreground placeholder:text-dim transition-colors duration-150 hover:border-border-hover focus:border-border-hover focus:outline-none focus:ring-1 focus:ring-white/10 disabled:opacity-50'

function SubjectCard({
  subject,
  isExpanded,
  onToggle,
  onSelect,
  isSelected,
}: {
  subject: FaceSubject
  isExpanded: boolean
  onToggle: () => void
  onSelect: () => void
  isSelected: boolean
}) {
  const rep = subject.representative_face

  return (
    <Card
      className={cn(
        'cursor-pointer transition-all',
        isSelected ? 'ring-2 ring-accent border-accent' : 'hover:border-border-hover',
      )}
    >
      <CardContent className="p-0">
        <div className="flex items-center gap-4 p-4">
          <button
            type="button"
            onClick={onSelect}
            className="shrink-0"
          >
            <div className="h-16 w-16 overflow-hidden rounded-lg bg-surface">
              <img
                src={`/api/media/file/${rep.media_hash}?case_id=${caseId}`}
                alt={subject.label || 'Sujeito'}
                className="h-full w-full object-cover"
                onError={(e) => {
                  ;(e.target as HTMLImageElement).style.display = 'none'
                }}
              />
            </div>
          </button>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-foreground">
                {subject.label || 'Sujeito desconhecido'}
              </span>
              <Badge variant="accent" className="text-[10px]">
                {subject.face_count} foto{subject.face_count > 1 ? 's' : ''}
              </Badge>
            </div>
            <div className="mt-1 flex items-center gap-3 text-xs text-dim">
              {rep.age && <span>{rep.age} anos</span>}
              {rep.gender && <span>{rep.gender === 'M' ? 'Masculino' : 'Feminino'}</span>}
              {rep.confidence && <span>{(rep.confidence * 100).toFixed(0)}% confiança</span>}
            </div>
          </div>

          <button
            type="button"
            onClick={onToggle}
            className="shrink-0 rounded-lg p-2 text-muted transition-colors hover:bg-white/5 hover:text-foreground"
          >
            {isExpanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </button>
        </div>

        {isExpanded && (
          <div className="border-t border-border px-4 py-4">
            <p className="mb-3 text-xs font-medium text-muted">
              Todas as fotos deste sujeito ({subject.faces.length})
            </p>
            <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-6">
              {subject.faces.map((face) => (
                <div
                  key={face.id}
                  className="aspect-square overflow-hidden rounded-lg bg-surface"
                >
                  <img
                    src={`/api/media/file/${face.media_hash}?case_id=${caseId}`}
                    alt={subject.label || 'Rosto'}
                    className="h-full w-full object-cover"
                    loading="lazy"
                    onError={(e) => {
                      ;(e.target as HTMLImageElement).style.display = 'none'
                    }}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function FacesTab({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient()
  const [expandedSubject, setExpandedSubject] = useState<string | null>(null)
  const [selectedSubject, setSelectedSubject] = useState<FaceSubject | null>(null)
  const [searchResults, setSearchResults] = useState<FaceSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [labelInput, setLabelInput] = useState('')
  const [showLabelFor, setShowLabelFor] = useState<string | null>(null)

  const { data: subjects = [], isLoading } = useQuery({
    queryKey: ['subjects', caseId],
    queryFn: () => apiListSubjects(caseId),
    enabled: !!caseId,
  })

  const labelMutation = useMutation({
    mutationFn: ({ faceId, label }: { faceId: string; label: string }) =>
      apiLabelFace(faceId, label),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subjects', caseId] })
      queryClient.invalidateQueries({ queryKey: ['faces', caseId] })
      setLabelInput('')
      setShowLabelFor(null)
    },
  })

  const searchMutation = useMutation({
    mutationFn: (faceId: string) => apiSearchFaces(caseId, faceId),
    onMutate: () => {
      setSearching(true)
      setSearchResults([])
    },
    onSuccess: (data) => {
      setSearchResults(data)
      setSearching(false)
    },
    onError: () => {
      setSearching(false)
    },
  })

  const totalFaces = subjects.reduce((acc, s) => acc + s.face_count, 0)

  return (
    <>
      <PageHeader
        icon={User}
        title="Sujeitos"
        description={`${subjects.length} sujeito(s) único(s) · ${totalFaces} foto(s) total`}
      />

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-5 w-5 animate-spin text-muted" />
        </div>
      ) : subjects.length === 0 ? (
        <EmptyState
          icon={User}
          title="Nenhum rosto detectado"
          description="Execute o pipeline de detecção na aba Mídia para analisar imagens."
        />
      ) : (
        <div className="space-y-3">
          {subjects.map((subject) => (
            <SubjectCard
              key={subject.subject_id}
              subject={subject}
              isExpanded={expandedSubject === subject.subject_id}
              onToggle={() =>
                setExpandedSubject(
                  expandedSubject === subject.subject_id ? null : subject.subject_id,
                )
              }
              onSelect={() => {
                setSelectedSubject(subject)
                searchMutation.mutate(subject.representative_face.id)
              }}
              isSelected={selectedSubject?.subject_id === subject.subject_id}
            />
          ))}
        </div>
      )}

      {selectedSubject && (
        <Card className="mt-4 border-accent/30">
          <CardContent className="p-4">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="h-14 w-14 overflow-hidden rounded-lg bg-surface">
                  <img
                    src={`/api/media/file/${selectedSubject.representative_face.media_hash}?case_id=${caseId}`}
                    alt="Sujeito selecionado"
                    className="h-full w-full object-cover"
                  />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">
                    {selectedSubject.label || 'Sujeito selecionado'}
                  </p>
                  <p className="text-xs text-dim">
                    Buscando correspondências em outros casos...
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setSelectedSubject(null)
                  setSearchResults([])
                }}
                className="rounded-lg p-2 text-muted hover:bg-white/5"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mb-3 flex gap-2">
              <input
                type="text"
                value={labelInput}
                onChange={(e) => setLabelInput(e.target.value)}
                placeholder="Nome do sujeito (ex: João)"
                className={cn('flex-1 h-9 rounded-md border border-border bg-surface px-3 text-sm')}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && labelInput.trim() && selectedSubject) {
                    labelMutation.mutate({
                      faceId: selectedSubject.representative_face.id,
                      label: labelInput.trim(),
                    })
                  }
                }}
              />
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  if (labelInput.trim() && selectedSubject) {
                    labelMutation.mutate({
                      faceId: selectedSubject.representative_face.id,
                      label: labelInput.trim(),
                    })
                  }
                }}
                disabled={!labelInput.trim()}
              >
                Rotular
              </Button>
            </div>

            {searching ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-4 w-4 animate-spin text-muted" />
                <span className="ml-2 text-sm text-muted">Buscando correspondências...</span>
              </div>
            ) : searchResults.length > 0 ? (
              <div>
                <p className="mb-2 text-xs font-medium text-muted">
                  {searchResults.length} correspondência(s) em outros casos
                </p>
                <div className="space-y-2">
                  {searchResults.map((result) => (
                    <div
                      key={result.face_id}
                      className="flex items-center gap-3 rounded-lg border border-border p-2"
                    >
                      <div className="h-10 w-10 shrink-0 overflow-hidden rounded bg-surface">
                        <img
                          src={`/api/media/file/${result.media_hash}?case_id=${caseId}`}
                          alt="Encontrado"
                          className="h-full w-full object-cover"
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="truncate text-xs font-medium text-foreground">
                          {result.label || result.case_name}
                        </p>
                        <p className="text-[10px] text-dim">
                          {(result.similarity * 100).toFixed(1)}% similar · Caso: {result.case_name}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : selectedSubject && !searching ? (
              <p className="py-4 text-center text-xs text-dim">
                Nenhuma correspondência encontrada em outros casos.
              </p>
            ) : null}
          </CardContent>
        </Card>
      )}
    </>
  )
}
