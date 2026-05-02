import { create } from 'zustand'
import type { Session, Flag, Claim, Utterance } from '@/contracts/types'

export type WsStatus = 'disconnected' | 'connecting' | 'connected' | 'reconnecting'
export type SessionStatus = 'armed' | 'active' | 'ended' | null

export interface LiveFlag {
  flag: Flag
  claim: Claim
  utterance: Utterance
  ts: number
  dismissed: boolean
}

interface SessionState {
  session: Session | null
  wsStatus: WsStatus
  sessionStatus: SessionStatus
  flags: LiveFlag[]
  score: number
  setSession: (s: Session) => void
  clearSession: () => void
  setWsStatus: (s: WsStatus) => void
  setSessionStatus: (s: SessionStatus) => void
  addFlag: (flag: Flag, claim: Claim, utterance: Utterance) => void
  dismissFlag: (flagId: string) => void
  setScore: (score: number) => void
}

export const useSessionStore = create<SessionState>()((set) => ({
  session: null,
  wsStatus: 'disconnected',
  sessionStatus: null,
  flags: [],
  score: 0,

  setSession(session) {
    set({ session })
  },

  clearSession() {
    set({ session: null, sessionStatus: null, flags: [], score: 0 })
  },

  setWsStatus(wsStatus) {
    set({ wsStatus })
  },

  setSessionStatus(sessionStatus) {
    set({ sessionStatus })
  },

  addFlag(flag, claim, utterance) {
    set((state) => ({
      flags: [
        ...state.flags,
        { flag, claim, utterance, ts: Date.now(), dismissed: false },
      ],
    }))
  },

  dismissFlag(flagId) {
    set((state) => ({
      flags: state.flags.map((f) =>
        f.flag.id === flagId ? { ...f, dismissed: true } : f,
      ),
    }))
  },

  setScore(score) {
    set({ score })
  },
}))
