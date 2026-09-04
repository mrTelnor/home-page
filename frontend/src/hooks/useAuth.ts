import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "@/api/client";
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
      } catch (err) {
        // Только 401 = «не авторизован». Сетевой сбой/500 не должны разлогинивать —
        // пробрасываем как ошибку запроса (isError), сессию не трогаем.
        if (err instanceof ApiError && err.status === 401) {
          clearUser();
          return null;
        }
        throw err;
      }
    },
    // не ретраим 401 (это валидный ответ), но повторяем сетевые/5xx
    retry: (count, err) =>
      !(err instanceof ApiError && err.status < 500) && count < 2,
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
