import { LogOut } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { Separator } from '@/components/ui/Separator'
import { cn } from '@/lib/cn'

export function UserMenu() {
  const { logout, userId } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const initial = userId ? userId.slice(0, 1).toUpperCase() : 'O'
  const displayId = userId ? userId.slice(0, 8) : 'operador'

  return (
    <div className="shrink-0 px-3 pb-[max(1.5rem,env(safe-area-inset-bottom,0px))] pt-3">
      <Separator className="mb-3" />
      <div className="mb-3 flex items-center gap-3 px-3 py-1">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-border bg-surface-elevated text-xs font-medium text-muted">
          {initial}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs font-medium text-foreground">Operador</p>
          <p className="truncate font-mono text-[11px] text-dim">{displayId}</p>
        </div>
      </div>
      <button
        type="button"
        onClick={handleLogout}
        className={cn(
          'flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium',
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
