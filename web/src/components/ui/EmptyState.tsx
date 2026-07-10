import { type LucideIcon } from 'lucide-react'
import { type ReactNode } from 'react'
import { cn } from '@/lib/cn'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description?: string
  action?: ReactNode
  className?: string
  size?: 'default' | 'compact'
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
  size = 'default',
}: EmptyStateProps) {
  const compact = size === 'compact'

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center text-center',
        compact ? 'py-8' : 'py-16',
        className,
      )}
    >
      <div
        className={cn(
          'mb-4 flex items-center justify-center rounded-lg bg-white/5',
          compact ? 'h-10 w-10' : 'h-12 w-12',
        )}
      >
        <Icon className={cn('text-dim', compact ? 'h-5 w-5' : 'h-6 w-6')} />
      </div>
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description && <p className="mt-1.5 max-w-sm text-sm text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
