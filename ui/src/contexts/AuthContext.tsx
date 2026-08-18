import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { authApi, User } from '../api/client'
import { clearAuthToken, getAuthToken, setAuthToken } from '../lib/tokenStorage'

interface AuthContextType {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const loadUser = useCallback(async () => {
    const token = getAuthToken()
    if (!token) {
      try {
        const session = await authApi.refresh()
        setAuthToken(session.access_token)
        setUser(session.user)
      } catch {
        clearAuthToken()
        setUser(null)
      } finally {
        setIsLoading(false)
      }
      return
    }
    try {
      const userData = await authApi.getMe()
      setUser(userData)
    } catch {
      clearAuthToken()
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadUser()
  }, [loadUser])

  const login = async (email: string, password: string) => {
    const response = await authApi.login(email, password)
    setAuthToken(response.access_token)
    setUser(response.user)
  }

  const logout = async () => {
    try {
      await authApi.logout() // revoke the refresh token server-side + clear the cookie
    } finally {
      clearAuthToken()
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider
      value={{ user, isLoading, isAuthenticated: !!user, login, logout, refreshUser: loadUser }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
