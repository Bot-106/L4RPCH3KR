import { create } from 'zustand';
import type { Session, Flag, Claim, Utterance, Attendee, SessionStatusValue } from '@/contracts';

export interface ActiveFlag {
  flag: Flag;
  claim: Claim;
  utterance: Utterance;
  lockedOpen: boolean;
}

type WsStatus = 'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'paused';

interface SessionState {
  session: Session | null;
  sessionStatus: SessionStatusValue | null;
  partner: Attendee | null;
  larpScore: number;

  activeFlags: ActiveFlag[];       // flags in the live queue (not yet dismissed)
  allFlags: Flag[];                // accumulates over session lifetime
  allClaims: Claim[];
  allUtterances: Utterance[];

  wsStatus: WsStatus;

  // Actions
  setSession: (session: Session | null) => void;
  setSessionStatus: (status: SessionStatusValue, partner: Attendee | null) => void;
  setPartner: (partner: Attendee) => void;
  setLarpScore: (score: number) => void;
  pushFlag: (flag: Flag, claim: Claim, utterance: Utterance) => void;
  dismissFlag: (flagId: string) => void;
  lockFlag: (flagId: string) => void;
  setWsStatus: (status: WsStatus) => void;
  reset: () => void;
}

const initial = {
  session: null as Session | null,
  sessionStatus: null as SessionStatusValue | null,
  partner: null as Attendee | null,
  larpScore: 0,
  activeFlags: [] as ActiveFlag[],
  allFlags: [] as Flag[],
  allClaims: [] as Claim[],
  allUtterances: [] as Utterance[],
  wsStatus: 'disconnected' as WsStatus,
};

export const useSessionStore = create<SessionState>((set) => ({
  ...initial,

  setSession(session) {
    set({ session });
  },

  setSessionStatus(status, partner) {
    set({ sessionStatus: status, partner: partner ?? null });
  },

  setPartner(partner) {
    set({ partner });
  },

  setLarpScore(score) {
    set({ larpScore: score });
  },

  pushFlag(flag, claim, utterance) {
    set((s) => ({
      activeFlags: [
        ...s.activeFlags,
        { flag, claim, utterance, lockedOpen: false },
      ],
      allFlags: [...s.allFlags, flag],
      allClaims: [...s.allClaims, claim],
      allUtterances: s.allUtterances.some((u) => u.id === utterance.id)
        ? s.allUtterances
        : [...s.allUtterances, utterance],
    }));
  },

  dismissFlag(flagId) {
    set((s) => ({
      activeFlags: s.activeFlags.filter((f) => f.flag.id !== flagId),
    }));
  },

  lockFlag(flagId) {
    set((s) => ({
      activeFlags: s.activeFlags.map((f) =>
        f.flag.id === flagId ? { ...f, lockedOpen: true } : f,
      ),
    }));
  },

  setWsStatus(status) {
    set({ wsStatus: status });
  },

  reset() {
    set(initial);
  },
}));
