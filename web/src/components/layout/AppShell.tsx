import { Shield } from 'lucide-react'
import { type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { UserMenu } from '@/components/layout/UserMenu'
import { cn } from '@/lib/cn'

export interface NavItem {
  id: string
  label: string
  icon: React.ComponentType<{ className?: string }>
}

interface BreadcrumbItem {
  label: string
  href?: string
}

export type FooterStatusLevel = 'ok' | 'degraded' | 'offline'

interface AppShellProps {
  children: ReactNode
  navItems?: NavItem[]
  activeNavId?: string
  onNavChange?: (id: string) => void
  breadcrumbs?: BreadcrumbItem[]
  headerActions?: ReactNode
  backButton?: ReactNode
  footerStatus?: { level: FooterStatusLevel; label?: string }
  hideFooter?: boolean
  contentClassName?: string
  fullWidth?: boolean
  bare?: boolean
}

const footerDotClass: Record<FooterStatusLevel, string> = {
  ok: 'bg-success',
  degraded: 'bg-warning',
  offline: 'bg-dim',
}

export function AppShell({
  children,
  navItems,
  activeNavId,
  onNavChange,
  breadcrumbs = [],
  headerActions,
  backButton,
  footerStatus,
  hideFooter = false,
  contentClassName,
  fullWidth = false,
  bare = false,
}: AppShellProps) {
  const navigate = useNavigate()

  return (
    <div className="flex h-[100dvh] overflow-hidden bg-background">
      <aside className="flex h-full w-72 shrink-0 flex-col border-r border-border bg-surface">
        <div className="flex h-16 shrink-0 items-center gap-3 border-b border-border px-6">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/5">
            <Shield className="h-4 w-4 text-foreground" />
          </div>
          <span className="text-sm font-semibold tracking-tight text-foreground">SOKOL</span>
        </div>

        {backButton && <div className="shrink-0 px-5 pt-5">{backButton}</div>}

        {navItems && navItems.length > 0 && (
          <nav className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-5 py-5">
            {navItems.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                onClick={() => onNavChange?.(id)}
                className={cn(
                  'flex items-center gap-3 rounded-lg px-3.5 py-1.5 text-left text-sm font-medium transition-colors duration-150',
                  activeNavId === id
                    ? 'bg-white/5 text-foreground'
                    : 'text-muted hover:bg-white/5 hover:text-foreground',
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="truncate">{label}</span>
              </button>
            ))}
          </nav>
        )}

        {!navItems && <div className="min-h-0 flex-1" />}

        <UserMenu />
      </aside>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center justify-between gap-4 border-b border-border bg-surface px-12 lg:px-16">
          <div className="flex min-w-0 items-center gap-2 text-sm">
            {breadcrumbs.map((crumb, i) => (
              <span key={i} className="flex min-w-0 items-center gap-2">
                {i > 0 && <span className="shrink-0 text-dim">/</span>}
                {crumb.href ? (
                  <button
                    type="button"
                    onClick={() => navigate(crumb.href!)}
                    className="shrink-0 text-muted transition-colors hover:text-foreground"
                  >
                    {crumb.label}
                  </button>
                ) : (
                  <span className="truncate text-foreground">{crumb.label}</span>
                )}
              </span>
            ))}
          </div>
          {headerActions && (
            <div className="flex shrink-0 items-center gap-3">{headerActions}</div>
          )}
        </header>

        <main className={cn('min-h-0 flex-1 overflow-auto', contentClassName)}>
          {bare ? (
            children
          ) : (
            <div
              className={cn(
                'box-border w-full px-12 py-12 lg:px-16',
                !fullWidth && 'mx-auto max-w-5xl',
              )}
            >
              {children}
            </div>
          )}
        </main>

        {!hideFooter && (
          <footer className="flex min-h-11 shrink-0 items-center justify-between border-t border-border bg-surface px-12 py-3 text-[11px] text-dim/80 lg:px-16 pb-[max(0.75rem,env(safe-area-inset-bottom,0px))]">
            <span>SOKOL v0.1.0</span>
            {footerStatus && (
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    'h-1.5 w-1.5 rounded-full',
                    footerDotClass[footerStatus.level],
                  )}
                />
                <span>{footerStatus.label}</span>
              </div>
            )}
          </footer>
        )}
      </div>
    </div>
  )
}
