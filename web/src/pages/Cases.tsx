import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiListCases, apiCreateCase, apiHealth } from '@/lib/api'
import {
  FolderOpen,
  Plus,
  Search,
  Scale,
  Calendar,
  RefreshCw,
} from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Dialog } from '@/components/ui/Dialog'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { healthLevelFromStatus, healthStatusLabel } from '@/lib/healthStatus'

export default function Cases() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newRef, setNewRef] = useState('')
  const [filter, setFilter] = useState('')

  const { data: cases, isLoading, refetch } = useQuery({
    queryKey: ['cases'],
    queryFn: apiListCases,
  })

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: apiHealth,
    refetchInterval: 30000,
  })

  const healthLevel = healthLevelFromStatus(health?.status)

  const createMutation = useMutation({
    mutationFn: () => apiCreateCase(newName, newRef || undefined),
    onSuccess: (newCase: { id: string }) => {
      queryClient.invalidateQueries({ queryKey: ['cases'] })
      setShowCreate(false)
      setNewName('')
      setNewRef('')
      navigate(`/cases/${newCase.id}`)
    },
  })

  const filtered = cases?.filter(
    (c: { name: string; legal_ref?: string | null }) =>
      c.name.toLowerCase().includes(filter.toLowerCase()) ||
      (c.legal_ref && c.legal_ref.toLowerCase().includes(filter.toLowerCase())),
  )

  return (
    <AppShell
      breadcrumbs={[{ label: 'SOKOL', href: '/cases' }, { label: 'Casos' }]}
      footerStatus={{
        level: healthLevel,
        label: healthStatusLabel(healthLevel),
      }}
    >
      <PageHeader
        title="Casos"
        description={`${cases?.length ?? 0} caso(s) encontrado(s)`}
        actions={
          <>
            <Button variant="secondary" size="md" onClick={() => refetch()} title="Atualizar">
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button onClick={() => setShowCreate(true)}>
              <Plus className="h-4 w-4" />
              Novo caso
            </Button>
          </>
        }
      />

      <div className="relative mb-8">
        <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-dim" />
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filtrar por nome ou referência..."
          className="h-11 w-full rounded-lg border border-border bg-surface-elevated py-2.5 pl-11 pr-4 text-sm text-foreground placeholder:text-dim transition-colors duration-150 hover:border-border-hover focus:border-border-hover focus:outline-none focus:ring-1 focus:ring-white/10"
        />
      </div>

      <Dialog
        open={showCreate}
        onOpenChange={setShowCreate}
        title="Novo Caso"
        description="Crie um novo caso para iniciar a análise forense."
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowCreate(false)}>
              Cancelar
            </Button>
            <Button
              onClick={() => createMutation.mutate()}
              disabled={!newName || createMutation.isPending}
            >
              {createMutation.isPending ? 'Criando...' : 'Criar Caso'}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input
            label="Nome"
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Ex: Operação Fênix"
            autoFocus
          />
          <Input
            label="Referência Legal (opcional)"
            type="text"
            value={newRef}
            onChange={(e) => setNewRef(e.target.value)}
            placeholder="Ex: 2026/00142"
          />
        </div>
      </Dialog>

      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      )}

      {!isLoading && filtered?.length === 0 && (
        <EmptyState
          icon={FolderOpen}
          title={filter ? 'Nenhum caso encontrado' : 'Nenhum caso ainda'}
          description={
            filter
              ? 'Tente outro termo de busca.'
              : 'Crie seu primeiro caso para começar a análise.'
          }
          action={
            !filter ? (
              <Button onClick={() => setShowCreate(true)}>
                <Plus className="h-4 w-4" />
                Criar primeiro caso
              </Button>
            ) : undefined
          }
        />
      )}

      <div className="space-y-3">
        {filtered?.map((c) => (
          <Card
            key={c.id}
            className="cursor-pointer hover:border-border-hover"
            onClick={() => navigate(`/cases/${c.id}`)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && navigate(`/cases/${c.id}`)}
          >
            <CardContent>
              <div className="flex items-start justify-between gap-6">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-3">
                    <h3 className="truncate text-base font-medium text-foreground">{c.name}</h3>
                    <Badge variant="success">{c.status}</Badge>
                  </div>
                  {c.legal_ref && (
                    <div className="mt-3 flex items-center gap-2 text-sm text-muted">
                      <Scale className="h-4 w-4 shrink-0 text-dim" />
                      <span className="break-words">{c.legal_ref}</span>
                    </div>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-2 text-sm text-dim">
                  <Calendar className="h-4 w-4" />
                  <span className="whitespace-nowrap">
                    {new Date(c.created_at).toLocaleDateString('pt-BR')}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </AppShell>
  )
}
