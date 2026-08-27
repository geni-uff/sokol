import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Navigate } from 'react-router-dom'
import { Database, Cpu, ShieldCheck, Loader2 } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import {
  apiAdminModels,
  apiAuditVerify,
  apiBackupSchedule,
  apiCreateBackup,
  apiListBackups,
  apiRestoreBackup,
  apiSetBackupSchedule,
  apiSwitchEmbed,
  apiSwitchLlm,
  apiSwitchReranker,
} from '@/lib/api'
import { AppShell } from '@/components/layout/AppShell'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'

export default function Admin() {
  const { isPlatformAdmin, isLogged } = useAuth()
  const queryClient = useQueryClient()
  const [freq, setFreq] = useState('weekly')
  const [retention, setRetention] = useState(7)
  const [error, setError] = useState('')

  const { data: backups } = useQuery({
    queryKey: ['admin-backups'],
    queryFn: apiListBackups,
    enabled: isPlatformAdmin,
  })
  const { data: schedule } = useQuery({
    queryKey: ['admin-backup-schedule'],
    queryFn: apiBackupSchedule,
    enabled: isPlatformAdmin,
  })
  const { data: models } = useQuery({
    queryKey: ['admin-models'],
    queryFn: apiAdminModels,
    enabled: isPlatformAdmin,
  })
  const { data: audit, refetch: refetchAudit } = useQuery({
    queryKey: ['admin-audit'],
    queryFn: apiAuditVerify,
    enabled: isPlatformAdmin,
  })

  const backupMut = useMutation({
    mutationFn: apiCreateBackup,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-backups'] }),
    onError: (e: Error) => setError(e.message),
  })
  const schedMut = useMutation({
    mutationFn: () =>
      apiSetBackupSchedule({ frequency: freq, retention_days: retention, enabled: true }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-backup-schedule'] }),
    onError: (e: Error) => setError(e.message),
  })
  const restoreMut = useMutation({
    mutationFn: (name: string) => apiRestoreBackup(name),
    onError: (e: Error) => setError(e.message),
  })
  const llmMut = useMutation({
    mutationFn: apiSwitchLlm,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-models'] }),
    onError: (e: Error) => setError(e.message),
  })
  const embedMut = useMutation({
    mutationFn: apiSwitchEmbed,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-models'] }),
    onError: (e: Error) => setError(e.message),
  })
  const rerankMut = useMutation({
    mutationFn: apiSwitchReranker,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-models'] }),
    onError: (e: Error) => setError(e.message),
  })

  if (!isLogged) return <Navigate to="/login" replace />
  if (!isPlatformAdmin) return <Navigate to="/cases" replace />

  const backupList = backups?.backups ?? []

  return (
    <AppShell breadcrumbs={[{ label: 'SOKOL', href: '/cases' }, { label: 'Administração' }]}>
      <PageHeader
        title="Administração"
        description="Backup, modelos e integridade da cadeia de auditoria"
      />

      {error && (
        <Card className="mb-6 border-danger/20">
          <CardContent className="py-3 text-sm text-danger">{error}</CardContent>
        </Card>
      )}

      <section className="mb-10">
        <h2 className="mb-4 flex items-center gap-2 text-sm font-medium text-foreground">
          <Database className="h-4 w-4" /> Backup
        </h2>
        <div className="mb-4 flex flex-wrap gap-3">
          <Button onClick={() => backupMut.mutate()} disabled={backupMut.isPending}>
            {backupMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Disparar backup
          </Button>
          <select
            value={freq}
            onChange={(e) => setFreq(e.target.value)}
            className="h-11 rounded-lg border border-border bg-surface-elevated px-3 text-sm"
          >
            <option value="daily">diário</option>
            <option value="weekly">semanal</option>
            <option value="monthly">mensal</option>
          </select>
          <input
            type="number"
            min={1}
            max={365}
            value={retention}
            onChange={(e) => setRetention(Number(e.target.value))}
            className="h-11 w-24 rounded-lg border border-border bg-surface-elevated px-3 text-sm"
          />
          <Button variant="secondary" onClick={() => schedMut.mutate()} disabled={schedMut.isPending}>
            Agendar
          </Button>
        </div>
        {schedule && (
          <p className="mb-4 text-xs text-dim">
            Agendamento: {String(schedule.frequency ?? '—')} · retenção{' '}
            {String(schedule.retention_days ?? '—')}d ·{' '}
            {schedule.enabled ? 'ativo' : 'inativo'}
          </p>
        )}
        <div className="space-y-2">
          {backupList.length === 0 ? (
            <p className="text-sm text-muted">Nenhum arquivo de backup.</p>
          ) : (
            backupList.map((b, i) => {
              const name = String(b.name ?? b.file ?? b.path ?? `backup-${i}`)
              return (
                <Card key={name}>
                  <CardContent className="flex items-center justify-between py-3">
                    <div>
                      <p className="font-mono text-sm text-foreground">{name}</p>
                      {b.size_bytes != null && (
                        <p className="text-xs text-dim">{String(b.size_bytes)} bytes</p>
                      )}
                    </div>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => {
                        if (
                          window.confirm(
                            'Restore apaga o banco atual. Continuar?',
                          )
                        ) {
                          restoreMut.mutate(name)
                        }
                      }}
                    >
                      Restore
                    </Button>
                  </CardContent>
                </Card>
              )
            })
          )}
        </div>
      </section>

      <section className="mb-10">
        <h2 className="mb-4 flex items-center gap-2 text-sm font-medium text-foreground">
          <Cpu className="h-4 w-4" /> Modelos
        </h2>
        {models?.effective_llm_model && (
          <p className="mb-4 text-sm text-dim">
            Chat usa <span className="font-mono text-foreground">{models.effective_llm_model}</span>
            {models.llm_n_ctx ? ` · n_ctx ${models.llm_n_ctx}` : ''}
          </p>
        )}
        {(
          [
            ['LLM', models?.llm_models ?? [], llmMut] as const,
            ['Embedding', models?.embedding_models ?? [], embedMut] as const,
            ['Reranker', models?.rerank_models ?? [], rerankMut] as const,
          ]
        ).map(([title, list, mut]) => (
          <div key={title} className="mb-5">
            <p className="mb-2 text-xs text-dim">{title}</p>
            <div className="space-y-2">
              {list.map((m) => (
                <Card key={m.id}>
                  <CardContent className="flex items-center justify-between py-3">
                    <div>
                      <span className="text-sm text-foreground">{m.model}</span>
                      <span className="ml-2 font-mono text-xs text-dim">{m.id}</span>
                    </div>
                    {m.active ? (
                      <Badge variant="success">ativo</Badge>
                    ) : (
                      <Button
                        size="sm"
                        variant="secondary"
                        disabled={mut.isPending}
                        onClick={() => mut.mutate(m.id)}
                      >
                        Ativar
                      </Button>
                    )}
                  </CardContent>
                </Card>
              ))}
              {list.length === 0 && <p className="text-sm text-muted">Nenhum modelo cadastrado.</p>}
            </div>
          </div>
        ))}
      </section>

      <section>
        <h2 className="mb-4 flex items-center gap-2 text-sm font-medium text-foreground">
          <ShieldCheck className="h-4 w-4" /> Integridade
        </h2>
        <div className="mb-3 flex items-center gap-3">
          <Button variant="secondary" onClick={() => refetchAudit()}>
            Verificar cadeia
          </Button>
          {audit && (
            <Badge variant={audit.valid ? 'success' : 'danger'}>
              {audit.valid ? 'íntegra' : 'falhas'}
            </Badge>
          )}
        </div>
        {audit && !audit.valid && (
          <pre className="overflow-auto rounded-lg border border-border p-3 text-xs text-danger">
            {JSON.stringify(audit.errors, null, 2)}
          </pre>
        )}
      </section>
    </AppShell>
  )
}
