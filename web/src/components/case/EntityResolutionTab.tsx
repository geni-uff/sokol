import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Users, Check, X, AlertTriangle, Loader2, GitMerge } from 'lucide-react'
import {
  apiSuggestResolutions,
  apiConfirmResolution,
  apiRejectResolution,
  type ResolutionSuggestion,
} from '@/lib/api'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 90 ? 'text-green-400' : pct >= 70 ? 'text-yellow-400' : 'text-orange-400'
  return <span className={`font-mono text-xs font-semibold ${color}`}>{pct}%</span>
}

function SuggestionCard({
  s,
  onConfirm,
  onReject,
  busy,
}: {
  s: ResolutionSuggestion
  onConfirm: (a: string, b: string) => void
  onReject: (a: string, b: string) => void
  busy: boolean
}) {
  return (
    <Card className="border-border hover:border-border-hover">
      <CardContent className="py-4 space-y-3">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge className="text-[10px] capitalize">{s.kind_a}</Badge>
              <span className="font-medium text-sm text-foreground truncate">
                {s.display_a ?? s.entity_a.slice(0, 8)}
              </span>
              <GitMerge className="h-3.5 w-3.5 text-dim shrink-0" />
              <Badge className="text-[10px] capitalize">{s.kind_b}</Badge>
              <span className="font-medium text-sm text-foreground truncate">
                {s.display_b ?? s.entity_b.slice(0, 8)}
              </span>
            </div>
            <p className="mt-1.5 text-xs text-muted">{s.reason}</p>
          </div>
          <ConfidenceBadge value={s.confidence} />
        </div>

        <div className="flex items-center gap-2 border-t border-border pt-3">
          <Button
            size="sm"
            onClick={() => onConfirm(s.entity_a, s.entity_b)}
            disabled={busy}
            className="gap-1.5"
          >
            <Check className="h-3.5 w-3.5" />
            Confirmar
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onReject(s.entity_a, s.entity_b)}
            disabled={busy}
            className="gap-1.5"
          >
            <X className="h-3.5 w-3.5" />
            Rejeitar
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function EntityResolutionTab({ caseId }: { caseId: string }) {
  const qc = useQueryClient()
  const [dismissed, setDismissed] = useState<Set<string>>(new Set())

  const {
    data,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['entity-resolution', caseId],
    queryFn: () => apiSuggestResolutions(caseId),
    enabled: !!caseId,
    staleTime: 60_000,
  })

  const confirmMut = useMutation({
    mutationFn: ({ a, b }: { a: string; b: string }) => apiConfirmResolution(a, b),
    onSuccess: (_data, { a, b }) => {
      setDismissed((prev) => new Set([...prev, `${a}:${b}`]))
      qc.invalidateQueries({ queryKey: ['entity-resolution', caseId] })
      qc.invalidateQueries({ queryKey: ['graph', caseId] })
    },
  })

  const rejectMut = useMutation({
    mutationFn: ({ a, b }: { a: string; b: string }) => apiRejectResolution(a, b),
    onSuccess: (_data, { a, b }) => {
      setDismissed((prev) => new Set([...prev, `${a}:${b}`]))
    },
  })

  const isBusy = confirmMut.isPending || rejectMut.isPending

  const visible = (data?.suggestions ?? []).filter(
    (s) => !dismissed.has(`${s.entity_a}:${s.entity_b}`),
  )

  return (
    <>
      <PageHeader
        icon={Users}
        title="Resolução de Entidades"
        description="Sugestões automáticas de identidade compartilhada entre entidades do caso"
        actions={
          <Button variant="secondary" size="sm" onClick={() => refetch()} disabled={isFetching}>
            {isFetching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Atualizar'}
          </Button>
        }
      />

      <div className="mb-4 flex items-start gap-3 rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-4 py-3">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-400" />
        <p className="text-xs text-yellow-300/80">
          Estas são sugestões automáticas (Indicators) — nunca afirmações de fato. Confirme
          manualmente antes de vincular duas entidades.
        </p>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-5 w-5 animate-spin text-muted" />
        </div>
      ) : visible.length === 0 ? (
        <EmptyState
          icon={Users}
          title="Nenhuma sugestão de resolução"
          description={
            dismissed.size > 0
              ? `${dismissed.size} sugestão(ões) processada(s) nesta sessão.`
              : 'Ingira dados com múltiplos sujeitos para ver sugestões de identidade compartilhada.'
          }
        />
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-dim">
            {visible.length} sugestão(ões) · Clique em Confirmar para criar aresta{' '}
            <code className="rounded bg-white/5 px-1 text-[10px]">resolves_to</code>
          </p>
          {visible.map((s) => (
            <SuggestionCard
              key={`${s.entity_a}:${s.entity_b}`}
              s={s}
              busy={isBusy}
              onConfirm={(a, b) => confirmMut.mutate({ a, b })}
              onReject={(a, b) => rejectMut.mutate({ a, b })}
            />
          ))}
        </div>
      )}

      {(confirmMut.error || rejectMut.error) && (
        <p className="mt-4 text-xs text-red-400">
          Erro: {((confirmMut.error || rejectMut.error) as Error).message}
        </p>
      )}
    </>
  )
}
