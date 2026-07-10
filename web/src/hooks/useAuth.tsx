import { createContext, useContext, useState, useEffect, useMemo, type ReactNode } from 'react'
import { apiLogin, logout as apiLogout } from '@/lib/api'

interface AuthContextType {
  token: string | null
  userId: string | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  isLogged: boolean
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('sokol_token'))
  const [userId, setUserId] = useState<string | null>(() => localStorage.getItem('sokol_user_id'))

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
  }, [token, userId])

  const login = async (username: string, password: string) => {
    const res = await apiLogin(username, password)
    setToken(res.token)
    setUserId(res.user_id)
  }

  const logout = () => {
    apiLogout()
    setToken(null)
    setUserId(null)
  }

  const isLogged = useMemo(() => !!token && !!userId, [token, userId])

  return (
    <AuthContext.Provider value={{ token, userId, login, logout, isLogged }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
