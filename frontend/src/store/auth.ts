import { create } from "zustand";

export interface User {
  id: string;
  username: string;
  role: string;
  created_at: string;
  tg_id: number | null;
  first_name: string | null;
  birthday: string | null;
  is_volkov: boolean;
  gender: "male" | "female" | null;
}

interface AuthState {
  user: User | null;
  setUser: (user: User) => void;
  clearUser: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  setUser: (user) => set({ user }),
  clearUser: () => set({ user: null }),
}));
