import { type LucideIcon } from 'lucide-react'
import { type ReactNode } from 'react'
import { cn } from '@/lib/cn'

interface PageHeaderProps {
  icon?: LucideIcon
  title: string
  description?: string
  actions?: ReactNode
  className?: string
}

export function PageHeader({ icon: Icon, title, description, actions, className }: PageHeaderProps) {
  return (
    <div
      className={cn(
        'mb-12 flex flex-col gap-6 md:flex-row md:items-start md:justify-between',
        className,
      )}
    >
      <div className="flex min-w-0 items-start gap-4">
        {Icon && (
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/5">
            <Icon className="h-5 w-5 text-muted" />
          </div>
        )}
        <div className="min-w-0">
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h2>
          {description && <p className="mt-1.5 text-sm text-muted">{description}</p>}
        </div>
      </div>
      {actions && (
        <div className="flex shrink-0 flex-wrap items-center gap-3 md:justify-end">
          {actions}
        </div>
      )}
    </div>
  )
}
