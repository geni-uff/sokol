import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Loader2, MessageSquare, Pencil, Trash2 } from 'lucide-react'
import {
  apiCreateComment,
  apiDeleteComment,
  apiListComments,
  apiUpdateComment,
  type CaseComment,
  type CommentTargetKind,
} from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn } from '@/lib/cn'

function relativeTime(iso: string): string {
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return iso
  const diffSec = Math.round((Date.now() - t) / 1000)
  if (diffSec < 60) return 'agora'
  const min = Math.round(diffSec / 60)
  if (min < 60) return `há ${min} min`
  const h = Math.round(min / 60)
  if (h < 24) return `há ${h} h`
  const d = Math.round(h / 24)
  if (d < 30) return `há ${d} d`
  return new Date(iso).toLocaleString('pt-BR')
}

function CommentItem({
  comment,
  canWrite,
  viewerUserId,
  viewerRole,
  onChanged,
}: {
  comment: CaseComment
  canWrite: boolean
  viewerUserId: string
  viewerRole: string
  onChanged: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(comment.body)
  const [busy, setBusy] = useState(false)
  const isAuthor = comment.author_user_id === viewerUserId
  const canEdit = canWrite && isAuthor
  const canDelete = canWrite && (isAuthor || viewerRole === 'admin')

  const save = async () => {
    if (!draft.trim()) return
    setBusy(true)
    try {
      await apiUpdateComment(comment.id, draft.trim())
      setEditing(false)
      onChanged()
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    setBusy(true)
    try {
      await apiDeleteComment(comment.id)
      onChanged()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-lg border border-border px-3 py-2.5" style={{ backgroundColor: '#141414' }}>
      <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-dim">
        <span className="font-medium text-muted">{comment.author_username}</span>
        <span>{relativeTime(comment.created_at)}</span>
        {comment.edited_at && <span className="italic">(editado)</span>}
        <span className="ml-auto flex gap-1">
          {canEdit && !editing && (
            <button
              type="button"
              className="rounded p-1 text-dim hover:bg-white/5 hover:text-foreground"
              onClick={() => {
                setDraft(comment.body)
                setEditing(true)
              }}
              aria-label="Editar"
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
          )}
          {canDelete && (
            <button
              type="button"
              className="rounded p-1 text-dim hover:bg-white/5 hover:text-danger"
              onClick={remove}
              disabled={busy}
              aria-label="Excluir"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </span>
      </div>
      {editing ? (
        <div className="space-y-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
          />
          <div className="flex gap-2">
            <Button size="sm" onClick={save} disabled={busy || !draft.trim()}>
              Salvar
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setEditing(false)} disabled={busy}>
              Cancelar
            </Button>
          </div>
        </div>
      ) : (
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">{comment.body}</p>
      )}
    </div>
  )
}

export function CaseCommentsPanel({
  caseId,
  targetKind,
  targetId,
  title = 'Notas',
  compact = false,
  className,
}: {
  caseId: string
  targetKind: CommentTargetKind
  targetId?: string | null
  title?: string
  compact?: boolean
  className?: string
}) {
  const queryClient = useQueryClient()
  const { userId } = useAuth()
  const [draft, setDraft] = useState('')

  const queryKey = ['comments', caseId, targetKind, targetId ?? null]

  const { data, isLoading, error } = useQuery({
    queryKey,
    queryFn: () =>
      apiListComments(caseId, {
        target_kind: targetKind,
        target_id: targetId ?? undefined,
      }),
    enabled: !!caseId,
  })

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['comments', caseId] })
  }

  const createMutation = useMutation({
    mutationFn: () =>
      apiCreateComment(caseId, {
        target_kind: targetKind,
        target_id: targetKind === 'case' ? null : targetId,
        body: draft.trim(),
      }),
    onSuccess: () => {
      setDraft('')
      invalidate()
    },
  })

  const comments = data?.comments ?? []
  const canWrite = data?.can_write ?? false
  const viewerRole = data?.viewer_role ?? 'leitor'
  const viewerUserId = data?.viewer_user_id ?? userId ?? ''

  return (
    <div className={cn(compact ? 'space-y-2' : 'space-y-4', className)}>
      {!compact && (
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-muted" />
          <h3 className="text-sm font-medium text-foreground">{title}</h3>
          <span className="text-xs text-dim">{comments.length}</span>
        </div>
      )}

      {isLoading ? (
        <div className="flex justify-center py-6">
          <Loader2 className="h-4 w-4 animate-spin text-muted" />
        </div>
      ) : error ? (
        <p className="text-sm text-danger">{error instanceof Error ? error.message : 'Erro ao carregar notas'}</p>
      ) : comments.length === 0 ? (
        <EmptyState icon={MessageSquare} title="Nenhuma nota ainda" />
      ) : (
        <div className="space-y-2">
          {comments.map((c) => (
            <CommentItem
              key={c.id}
              comment={c}
              canWrite={canWrite}
              viewerUserId={viewerUserId}
              viewerRole={viewerRole}
              onChanged={invalidate}
            />
          ))}
        </div>
      )}

      {canWrite && (
        <div className="space-y-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={compact ? 2 : 3}
            placeholder="Escrever nota interna…"
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-dim"
          />
          <Button
            size="sm"
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending || !draft.trim()}
          >
            {createMutation.isPending ? 'Salvando…' : 'Adicionar nota'}
          </Button>
          {createMutation.isError && (
            <p className="text-xs text-danger">
              {createMutation.error instanceof Error
                ? createMutation.error.message
                : 'Falha ao criar nota'}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

/** Badge/button that opens an inline comment list for a timeline event. */
export function EventCommentToggle({
  caseId,
  eventId,
  count = 0,
}: {
  caseId: string
  eventId: string
  count?: number
}) {
  const [open, setOpen] = useState(false)

  return (
    <div className="mt-2 w-full">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-dim transition-colors hover:bg-white/5 hover:text-foreground"
      >
        <MessageSquare className="h-3.5 w-3.5" />
        {count > 0 ? `${count} nota${count === 1 ? '' : 's'}` : 'Notas'}
      </button>
      {open && (
        <Card className="mt-2 border-border">
          <CardContent className="py-3">
            <CaseCommentsPanel
              caseId={caseId}
              targetKind="event"
              targetId={eventId}
              compact
            />
          </CardContent>
        </Card>
      )}
    </div>
  )
}
