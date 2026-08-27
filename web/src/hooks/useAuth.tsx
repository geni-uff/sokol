import { createContext, useContext, useState, useEffect, useMemo, type ReactNode } from 'react'
import { apiLogin, logout as apiLogout } from '@/lib/api'

interface AuthContextType {
  token: string | null
  userId: string | null
  isPlatformAdmin: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  isLogged: boolean
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('sokol_token'))
  const [userId, setUserId] = useState<string | null>(() => localStorage.getItem('sokol_user_id'))
  const [isPlatformAdmin, setIsPlatformAdmin] = useState(
    () => localStorage.getItem('sokol_is_platform_admin') === '1',
  )

  useEffect(() => {
    if (token) {
      localStorage.setItem('sokol_token', token)
    } else {
      localStorage.removeItem('sokol_token')
    }
    if (userId) {
      localStorage.setItem('sokol_user_id', userId)
    } else {
      localStorage.removeItem('sokol_user_id')
    }
    if (isPlatformAdmin) {
      localStorage.setItem('sokol_is_platform_admin', '1')
    } else {
      localStorage.removeItem('sokol_is_platform_admin')
    }
  }, [token, userId, isPlatformAdmin])

  const login = async (username: string, password: string) => {
    const res = await apiLogin(username, password)
    setToken(res.token)
    setUserId(res.user_id)
    setIsPlatformAdmin(Boolean(res.is_platform_admin))
  }

  const logout = () => {
    apiLogout()
    setToken(null)
    setUserId(null)
    setIsPlatformAdmin(false)
  }

  const isLogged = useMemo(() => !!token && !!userId, [token, userId])

  return (
    <AuthContext.Provider value={{ token, userId, isPlatformAdmin, login, logout, isLogged }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
