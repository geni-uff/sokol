export type HealthLevel = 'ok' | 'degraded' | 'offline'

export function healthLevelFromStatus(status?: string): HealthLevel {
  if (status === 'ok') return 'ok'
  if (status === 'degraded' || status === 'warning') return 'degraded'
  return 'offline'
}

export function healthStatusLabel(level: HealthLevel): string {
  switch (level) {
    case 'ok':
      return 'API conectada'
    case 'degraded':
      return 'Serviços degradados'
    case 'offline':
      return 'Sem conexão'
  }
}
