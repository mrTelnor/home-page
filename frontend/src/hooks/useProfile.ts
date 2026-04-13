import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { type User } from "@/store/auth";

export interface TelegramAuthData {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
}

export function useTelegramVerify() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: TelegramAuthData) =>
      api.post<User>("/api/auth/telegram-verify", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });
}

export function useTelegramUnlink() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => api.post<User>("/api/auth/telegram-unlink"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (data: { old_password: string; new_password: string }) =>
      api.post("/api/auth/change-password", data),
  });
}
