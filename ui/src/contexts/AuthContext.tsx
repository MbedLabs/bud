import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { authApi, User } from '../api/client'
import {
  clearAuthToken,
  getAuthToken,
  getSessionUserId,
  setAuthToken,
  setSessionUserId,
} from '../lib/tokenStorage'

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
  const queryClient = useQueryClient()
  const currentUser = useRef<User | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const applyUser = useCallback(
    (next: User | null) => {
      const previous = getSessionUserId()
      if (previous !== null && previous !== (next?.id ?? null)) {
        clearAuthToken()
        queryClient.clear()
        setSessionUserId(null)
        currentUser.current = null
        setUser(null)
        window.location.replace('/login')
        return
      }
      if (previous === null && next !== null) {
        queryClient.clear()
      }
      const sameUser = currentUser.current?.id === next?.id && next !== null
      if (sameUser && (
        currentUser.current?.profile_picture_url !== next.profile_picture_url ||
        currentUser.current?.has_profile_picture !== next.has_profile_picture
      )) {
        for (const key of ['users', 'audit', 'groups', 'access-users', 'access-requests']) {
          void queryClient.invalidateQueries({ queryKey: [key] })
        }
      }
      setSessionUserId(next?.id ?? null)
      currentUser.current = next
      setUser(next)
    },
    [queryClient],
  )

  const loadUser = useCallback(async () => {
    try {
      if (getAuthToken()) {
        applyUser(await authApi.getMe())
      } else {
        const session = await authApi.refresh()
        setAuthToken(session.access_token)
        applyUser(session.user)
      }
    } catch {
      clearAuthToken()
      applyUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [applyUser])

  const loadStarted = useRef(false)

  useEffect(() => {
    if (loadStarted.current) return
    loadStarted.current = true
    loadUser()
  }, [loadUser])

  const login = async (email: string, password: string) => {
    const response = await authApi.login(email, password)
    setSessionUserId(null)
    setAuthToken(response.access_token)
    applyUser(response.user)
  }

  const logout = async () => {
    try {
      await authApi.logout()
    } finally {
      clearAuthToken()
      applyUser(null)
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
