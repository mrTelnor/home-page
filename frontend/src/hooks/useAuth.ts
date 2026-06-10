import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "@/api/client";
import { endpoints } from "@/api/endpoints";
import { type User } from "@/api/types";
import { useAuthStore } from "@/store/auth";

export function useMe() {
  const setUser = useAuthStore((s) => s.setUser);
  const clearUser = useAuthStore((s) => s.clearUser);

  return useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        const user = await api.get<User>(endpoints.auth.me);
        setUser(user);
        return user;
      } catch {
        clearUser();
        return null;
      }
    },
    retry: false,
    staleTime: 1000 * 60 * 5,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (data: { username: string; password: string }) =>
      api.post(endpoints.auth.login, data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      navigate("/");
    },
  });
}

export function useRegister() {
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (data: { username: string; password: string; invite_code: string }) =>
      api.post(endpoints.auth.register, data),
    onSuccess: () => {
      navigate("/login");
    },
  });
}

export function useLogout() {
  const clearUser = useAuthStore((s) => s.clearUser);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: () => api.post(endpoints.auth.logout),
    onSuccess: () => {
      clearUser();
      queryClient.clear();
      navigate("/login");
    },
  });
}
