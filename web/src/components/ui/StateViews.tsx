import { type LucideIcon } from 'lucide-react'
import { type ReactNode } from 'react'
import { AlertTriangle, Ban, Loader2 } from 'lucide-react'
import { cn } from '@/lib/cn'

interface StateBlockProps {
  icon: LucideIcon
  title: string
  description?: string
  action?: ReactNode
  className?: string
  tone?: 'default' | 'danger' | 'warning'
}

function StateBlock({
  icon: Icon,
  title,
  description,
  action,
  className,
  tone = 'default',
}: StateBlockProps) {
  const iconTone =
    tone === 'danger' ? 'text-red-400' : tone === 'warning' ? 'text-amber-400' : 'text-dim'

  return (
    <div className={cn('flex flex-col items-center justify-center py-16 text-center', className)}>
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-white/5">
        <Icon className={cn('h-6 w-6', iconTone)} />
      </div>
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description && <p className="mt-1.5 max-w-sm text-sm text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

/** Loading — seção 8.3 */
export function LoadingState({
  title = 'Carregando…',
  description,
  className,
}: {
  title?: string
  description?: string
  className?: string
}) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-16 text-center', className)}>
      <Loader2 className="mb-4 h-6 w-6 animate-spin text-muted" />
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description && <p className="mt-1.5 max-w-sm text-sm text-muted">{description}</p>}
    </div>
  )
}

/** Erro recuperável — seção 8.3 */
export function ErrorState({
  title = 'Algo deu errado',
  description = 'Tente novamente em instantes.',
  action,
  className,
}: {
  title?: string
  description?: string
  action?: ReactNode
  className?: string
}) {
  return (
    <StateBlock
      icon={AlertTriangle}
      title={title}
      description={description}
      action={action}
      className={className}
      tone="danger"
    />
  )
}

/** Sem permissão — seção 8.3 */
export function ForbiddenState({
  title = 'Sem permissão',
  description = 'Você não tem acesso a este recurso.',
  action,
  className,
}: {
  title?: string
  description?: string
  action?: ReactNode
  className?: string
}) {
  return (
    <StateBlock
      icon={Ban}
      title={title}
      description={description}
      action={action}
      className={className}
      tone="warning"
    />
  )
}
