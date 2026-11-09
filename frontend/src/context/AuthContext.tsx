import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { usersApi } from '../api/service'
import type { User } from '../api/types'

interface AuthState {
  user: User | null
  loading: boolean
  isAdmin: boolean
  login: (email: string, password: string) => Promise<void>
  register: (data: { email: string; password: string; full_name: string; phone?: string }) => Promise<void>
  logout: () => void
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)
const TOKEN_KEY = 'marcheci_token'

function hasStoredToken(): boolean {
  try { return Boolean(localStorage.getItem(TOKEN_KEY)) } catch { return false }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(hasStoredToken)

  const refresh = useCallback(async () => {
    try {
      const { data } = await usersApi.me()
      setUser(data)
    } catch {
      localStorage.removeItem(TOKEN_KEY)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(() => { if (hasStoredToken()) void refresh() }, [refresh])

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await usersApi.login(email, password)
    localStorage.setItem(TOKEN_KEY, data.access_token)
    const me = await usersApi.me()
    setUser(me.data)
  }, [])

  const register = useCallback(async (payload: { email: string; password: string; full_name: string; phone?: string }) => {
    await usersApi.register(payload)
    await login(payload.email, payload.password)
  }, [login])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    setUser(null)
    // déconnexion côté client (JWT courts durée de vie ; révocation serveur non prévue)
  }, [])

  return (
    <AuthContext.Provider
      value={{ user, loading, isAdmin: user?.role === 'ADMIN', login, register, logout, refresh }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// oxlint-disable-next-line react/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth hors AuthProvider')
  return ctx
}
