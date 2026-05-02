import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/contracts/types'
import { setJwt, clearJwt, getJwt } from '@/lib/auth'

interface AuthState {
  user: User | null
  jwt: string | null
  isAuthed: boolean
  setAuth: (user: User, jwt: string) => void
  clearAuth: () => void
  setUser: (user: User) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      jwt: getJwt(),
      isAuthed: Boolean(getJwt()),

      setAuth(user, jwt) {
        setJwt(jwt)
        set({ user, jwt, isAuthed: true })
      },

      clearAuth() {
        clearJwt()
        set({ user: null, jwt: null, isAuthed: false })
      },

      setUser(user) {
        set({ user })
      },
    }),
    {
      name: 'auth-store',
      partialize: (state) => ({ user: state.user, jwt: state.jwt, isAuthed: state.isAuthed }),
      // After rehydration from localStorage, sync the standalone 'jwt' key so
      // the axios interceptor (which calls getJwt()) stays consistent with the
      // persisted store value.
      onRehydrateStorage: () => (state) => {
        if (state?.jwt) {
          setJwt(state.jwt)
        } else {
          clearJwt()
        }
      },
    },
  ),
)
