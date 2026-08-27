import { LogOut, Shield } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { Separator } from '@/components/ui/Separator'
import { cn } from '@/lib/cn'

export function UserMenu() {
  const { logout, userId, isPlatformAdmin } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const initial = userId ? userId.slice(0, 1).toUpperCase() : 'O'
  const displayId = userId ? userId.slice(0, 8) : 'operador'

  return (
    <div className="shrink-0 px-5 pt-5 pb-[max(2.5rem,calc(env(safe-area-inset-bottom,0px)+1.25rem))]">
      <Separator className="mb-5" />
      <div className="mb-4 flex items-center gap-3 px-3.5 py-2">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border bg-surface-elevated text-xs font-medium text-muted">
          {initial}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs font-medium text-foreground">Operador</p>
          <p className="truncate font-mono text-[11px] text-dim">{displayId}</p>
        </div>
      </div>
      {isPlatformAdmin && (
        <button
          type="button"
          onClick={() => navigate('/admin')}
          className={cn(
            'mb-1 flex w-full items-center gap-3 rounded-lg px-4 py-3.5 text-left text-sm font-medium',
            'text-muted transition-colors duration-150',
            'hover:bg-white/5 hover:text-foreground',
          )}
        >
          <Shield className="h-4 w-4 shrink-0" />
          <span className="truncate">Administração</span>
        </button>
      )}
      <button
        type="button"
        onClick={handleLogout}
        className={cn(
          'flex w-full items-center gap-3 rounded-lg px-4 py-3.5 text-left text-sm font-medium',
          'text-muted transition-colors duration-150',
          'hover:bg-white/5 hover:text-foreground',
        )}
      >
        <LogOut className="h-4 w-4 shrink-0" />
        <span className="truncate">Sair</span>
      </button>
    </div>
  )
}
