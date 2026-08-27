import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  FolderOpen,
  FileArchive,
  Inbox,
  Loader2,
  RefreshCw,
} from 'lucide-react'
import {
  apiBatchIngest,
  apiListInbox,
  apiListIngestJobs,
  type InboxFile,
} from '@/lib/api'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`
  return `${(n / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

function folderOf(file: InboxFile): string {
  const idx = file.path.lastIndexOf('/')
  return idx === -1 ? '' : file.path.slice(0, idx)
}

function statusVariant(status: string): 'success' | 'warning' | 'danger' | 'default' {
  switch (status) {
    case 'done':
    case 'completed':
      return 'success'
    case 'running':
    case 'pending':
    case 'importing':
      return 'warning'
    case 'failed':
      return 'danger'
    default:
      return 'default'
  }
}

export function IngestPanel({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [sourceType, setSourceType] = useState<'ufdr' | 'pdf'>('ufdr')

  const { data: inbox = [], isLoading: inboxLoading, refetch: refetchInbox } = useQuery({
    queryKey: ['ingest-inbox', sourceType],
    queryFn: () => apiListInbox(undefined, sourceType),
  })

  const { data: jobs = [], isLoading: jobsLoading } = useQuery({
    queryKey: ['ingest-jobs', caseId],
    queryFn: () => apiListIngestJobs(caseId),
    refetchInterval: (query) => {
      const rows = query.state.data
      const busy = rows?.some((j) => j.status === 'pending' || j.status === 'running')
      return busy ? 4000 : 15000
    },
  })

  const files = useMemo(() => inbox.filter((e) => !e.is_dir), [inbox])
  const grouped = useMemo(() => {
    const map = new Map<string, InboxFile[]>()
    for (const file of files) {
      const folder = folderOf(file)
      const list = map.get(folder) ?? []
      list.push(file)
      map.set(folder, list)
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [files])

  const ingestMutation = useMutation({
    mutationFn: (refs: string[]) => apiBatchIngest(caseId, refs, sourceType),
    onSuccess: () => {
      setSelected(new Set())
      queryClient.invalidateQueries({ queryKey: ['ingest-jobs', caseId] })
      queryClient.invalidateQueries({ queryKey: ['ops-health'] })
    },
  })

  function toggle(path: string) {
    const file = files.find((f) => f.path === path)
    if (file && file.ready === false) return
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  function toggleFolder(folder: string, folderFiles: InboxFile[]) {
    const readyFiles = folderFiles.filter((f) => f.ready !== false)
    const paths = readyFiles.map((f) => f.path)
    const allOn = paths.length > 0 && paths.every((p) => selected.has(p))
    setSelected((prev) => {
      const next = new Set(prev)
      for (const p of paths) {
        if (allOn) next.delete(p)
        else next.add(p)
      }
      return next
    })
  }

  const selectedCount = selected.size

  return (
    <div className="mb-16">
      <PageHeader
        icon={Inbox}
        title="Ingestão"
        description="Arquivos no inbox do host (SOKOL_INGEST_DIR). Selecione e enfileire neste caso. Arquivos ainda sendo copiados aparecem, mas não entram na ingestão."
        actions={
          <>
            <Button
              variant="secondary"
              size="lg"
              className="min-w-12 px-4"
              onClick={() => refetchInbox()}
              title="Atualizar inbox"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button
              size="lg"
              disabled={selectedCount === 0 || ingestMutation.isPending}
              onClick={() => ingestMutation.mutate([...selected])}
            >
              {ingestMutation.isPending
                ? 'Enfileirando…'
                : `Ingerir ${selectedCount || ''}`.trim()}
            </Button>
          </>
        }
      />

      <div className="mb-8 flex flex-wrap items-center gap-4">
        <label className="text-sm text-muted">
          Tipo
          <select
            className="ml-3 h-11 rounded-lg border border-border-hover bg-surface-elevated px-4 text-sm text-foreground"
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value === 'pdf' ? 'pdf' : 'ufdr')}
          >
            <option value="ufdr">UFDR</option>
            <option value="pdf">PDF</option>
          </select>
        </label>
        <p className="text-sm text-dim">
          Uma pasta no inbox (ex. <span className="font-mono">apple/pa7.ufdr</span>) entra
          inteira se você marcar o cabeçalho da pasta.
        </p>
      </div>

      {ingestMutation.isError && (
        <p className="mb-6 text-sm text-danger">
          {ingestMutation.error instanceof Error
            ? ingestMutation.error.message
            : 'Falha ao enfileirar'}
        </p>
      )}
      {ingestMutation.isSuccess && (
        <p className="mb-6 text-sm text-muted">
          {ingestMutation.data.queued} documento(s) na fila.
        </p>
      )}

      {inboxLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-5 w-5 animate-spin text-muted" />
        </div>
      ) : files.length === 0 ? (
        <EmptyState
          icon={FolderOpen}
          title="Inbox vazio"
          description="Copie .ufdr ou .pdf para SOKOL_INGEST_DIR (default UFDRsTest/, relativa a deploy/). Subpastas ok. Não precisa parar o Docker."
        />
      ) : (
        <div className="space-y-6">
          {grouped.map(([folder, folderFiles]) => {
            const allOn = folderFiles.every((f) => selected.has(f.path))
            const label = folder || 'Raiz do inbox'
            return (
              <Card key={folder || '__root'}>
                <CardContent className="p-6">
                  <div className="mb-4 flex items-center justify-between gap-4">
                    <button
                      type="button"
                      onClick={() => toggleFolder(folder, folderFiles)}
                      className="flex min-w-0 items-center gap-3 text-left text-sm font-medium text-foreground"
                    >
                      <span
                        className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border ${
                          allOn ? 'border-foreground bg-foreground' : 'border-border-hover'
                        }`}
                      />
                      <FolderOpen className="h-4 w-4 shrink-0 text-muted" />
                      <span className="truncate font-mono text-sm">{label}</span>
                      <span className="text-xs font-normal text-dim">
                        {folderFiles.length} arquivo(s)
                      </span>
                    </button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        ingestMutation.mutate(
                          folderFiles.filter((f) => f.ready !== false).map((f) => f.path),
                        )
                      }
                      disabled={
                        ingestMutation.isPending ||
                        folderFiles.every((f) => f.ready === false)
                      }
                    >
                      Ingerir pasta
                    </Button>
                  </div>
                  <ul className="space-y-1">
                    {folderFiles.map((file) => {
                      const on = selected.has(file.path)
                      const copying = file.ready === false
                      return (
                        <li key={file.path}>
                          <button
                            type="button"
                            onClick={() => toggle(file.path)}
                            disabled={copying}
                            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            <span
                              className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                                on ? 'border-foreground bg-foreground' : 'border-border-hover'
                              }`}
                            />
                            <FileArchive className="h-4 w-4 shrink-0 text-dim" />
                            <span className="min-w-0 flex-1 truncate font-mono text-foreground">
                              {file.name}
                            </span>
                            {copying && (
                              <Badge className="shrink-0 text-[10px]">Copiando</Badge>
                            )}
                            <span className="shrink-0 font-mono text-xs text-dim">
                              {formatBytes(file.size)}
                            </span>
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      <div className="mt-12">
        <h3 className="mb-4 text-sm font-medium text-foreground">Fila deste caso</h3>
        {jobsLoading ? (
          <Loader2 className="h-5 w-5 animate-spin text-muted" />
        ) : jobs.length === 0 ? (
          <p className="text-sm text-dim">Nenhum job de ingestão neste caso.</p>
        ) : (
          <div className="space-y-2">
            {jobs.map((job) => (
              <Card key={job.job_id}>
                <CardContent className="flex items-center justify-between gap-4 py-4">
                  <div className="min-w-0">
                    <p className="truncate font-mono text-sm text-foreground">
                      {job.inbox_ref ?? job.job_id}
                    </p>
                    {job.parse_coverage?.ignored_model_types &&
                      Object.keys(job.parse_coverage.ignored_model_types).length > 0 && (
                        <p className="mt-1 text-xs text-dim">
                          XML ignorado:{" "}
                          {Object.entries(job.parse_coverage.ignored_model_types)
                            .map(([t, n]) => `${t} (${n})`)
                            .join(", ")}
                        </p>
                      )}
                    {job.parse_coverage?.fs_walk && (
                      <p className="mt-1 text-xs text-dim">
                        FileSystem: {JSON.stringify(job.parse_coverage.fs_walk)}
                      </p>
                    )}
                    {job.error && (
                      <p className="mt-1 truncate text-xs text-danger">{job.error}</p>
                    )}
                  </div>
                  <Badge variant={statusVariant(job.status)}>{job.status}</Badge>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
