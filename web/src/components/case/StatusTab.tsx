import { useQuery } from '@tanstack/react-query'
import { Activity, AlertTriangle, CheckCircle } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardContent } from '@/components/ui/Card'
import { Loader2 } from 'lucide-react'

interface ServiceStatus {
  name: string
  status: string
  latency_ms?: number
  uptime_pct?: number
}

interface SystemMetrics {
  cpu_percent: number
  memory_percent: number
  disk_percent: number
}

interface MonitoringResponse {
  services: ServiceStatus[]
  system: SystemMetrics
  queued_jobs: number
  timestamp: string
}

async function apiGetMonitoringStatus(): Promise<MonitoringResponse> {
  const response = await fetch('/api/ops/monitoring/status', {
    headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
  })
  if (!response.ok) throw new Error('Failed to fetch monitoring status')
  return response.json()
}

export function StatusTab() {
  const { data: monitoring, isLoading } = useQuery({
    queryKey: ['monitoring'],
    queryFn: apiGetMonitoringStatus,
    refetchInterval: 10000,
  })

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-5 w-5 animate-spin text-muted" />
      </div>
    )
  }

  if (!monitoring) return null

  const getStatusIcon = (status: string) => {
    return status === 'up' ? (
      <CheckCircle className="h-4 w-4 text-green-500" />
    ) : status === 'slow' ? (
      <AlertTriangle className="h-4 w-4 text-yellow-500" />
    ) : (
      <AlertTriangle className="h-4 w-4 text-red-500" />
    )
  }

  return (
    <>
      <PageHeader
        icon={Activity}
        title="Status"
        description="System health and service status"
      />

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* Services */}
        <div>
          <h2 className="mb-4 text-lg font-semibold">Serviços</h2>
          <div className="space-y-2">
            {monitoring.services.map((service) => (
              <Card key={service.name} className="border-border">
                <CardContent className="flex items-center justify-between py-3">
                  <div className="flex items-center gap-3">
                    {getStatusIcon(service.status)}
                    <span className="font-medium">{service.name}</span>
                  </div>
                  <div className="text-xs text-dim">
                    {service.latency_ms && <span>{service.latency_ms.toFixed(1)}ms</span>}
                    {service.uptime_pct && <span> • {service.uptime_pct.toFixed(1)}% uptime</span>}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* System Metrics */}
        <div>
          <h2 className="mb-4 text-lg font-semibold">Recursos</h2>
          <div className="space-y-2">
            <Card className="border-border">
              <CardContent className="py-3">
                <div className="flex items-center justify-between">
                  <span>CPU</span>
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-24 rounded-full bg-surface-elevated">
                      <div
                        className="h-full rounded-full bg-blue-500"
                        style={{ width: `${monitoring.system.cpu_percent}%` }}
                      />
                    </div>
                    <span className="text-xs text-dim">{monitoring.system.cpu_percent.toFixed(1)}%</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-border">
              <CardContent className="py-3">
                <div className="flex items-center justify-between">
                  <span>Memória</span>
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-24 rounded-full bg-surface-elevated">
                      <div
                        className="h-full rounded-full bg-green-500"
                        style={{ width: `${monitoring.system.memory_percent}%` }}
                      />
                    </div>
                    <span className="text-xs text-dim">{monitoring.system.memory_percent.toFixed(1)}%</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-border">
              <CardContent className="py-3">
                <div className="flex items-center justify-between">
                  <span>Disco</span>
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-24 rounded-full bg-surface-elevated">
                      <div
                        className="h-full rounded-full bg-purple-500"
                        style={{ width: `${monitoring.system.disk_percent}%` }}
                      />
                    </div>
                    <span className="text-xs text-dim">{monitoring.system.disk_percent.toFixed(1)}%</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      <div className="mt-6">
        <Card className="border-border bg-surface-elevated/50">
          <CardContent className="py-4">
            <p className="text-sm text-dim">
              <strong>Fila de ingestão:</strong> {monitoring.queued_jobs} arquivos aguardando processamento
            </p>
            <p className="mt-2 text-xs text-dim">Última atualização: {new Date(monitoring.timestamp).toLocaleTimeString('pt-BR')}</p>
          </CardContent>
        </Card>
      </div>
    </>
  )
}
