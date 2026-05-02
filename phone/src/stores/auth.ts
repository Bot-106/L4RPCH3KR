import { create } from 'zustand';
import type { User } from '@/contracts';
import { loadJwt, saveJwt, clearJwt } from '@/services/auth';
import { setJwt as setApiJwt } from '@/services/api';
import { wsClient } from '@/services/ws';

interface AuthState {
  user: User | null;
  jwt: string | null;
  isLoading: boolean;

  hydrate: () => Promise<void>;
  signIn: (jwt: string, user: User) => Promise<void>;
  signOut: () => Promise<void>;
  updateUser: (user: User) => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  jwt: null,
  isLoading: true,

  async hydrate() {
    const jwt = await loadJwt();
    if (jwt) {
      setApiJwt(jwt);
      // User data fetched separately by the navigator once jwt is set
      set({ jwt, isLoading: false });
    } else {
      set({ isLoading: false });
    }
  },

  async signIn(jwt, user) {
    await saveJwt(jwt);
    setApiJwt(jwt);
    wsClient.setCredentials(jwt, user.id);
    set({ jwt, user });
  },

  async signOut() {
    wsClient.disconnect();
    await clearJwt();
    setApiJwt(null);
    set({ jwt: null, user: null });
  },

  updateUser(user) {
    set({ user });
    const { jwt } = get();
    if (jwt) {
      wsClient.setCredentials(jwt, user.id);
    }
  },
}));
