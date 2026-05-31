import { create } from 'zustand'

export const useAuthStore = create((set) => ({
  token: null,
  user: null,
  isAuthenticated: false,

  login: (token, user) => set({ token, user, isAuthenticated: true }),
  logout: () => set({ token: null, user: null, isAuthenticated: false }),
  updateUser: (updates) => set((s) => ({ user: { ...s.user, ...updates } })),
}))
