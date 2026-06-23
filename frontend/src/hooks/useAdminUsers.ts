import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { endpoints } from "@/api/endpoints";
import { type AdminUserRow } from "@/api/types";

export function useAdminUsers() {
  return useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => api.get<AdminUserRow[]>(endpoints.admin.users),
  });
}

export function useAdminResetLink() {
  return useMutation({
    mutationFn: (userId: string) =>
      api.post<{ link: string; expires_at: string }>(endpoints.admin.resetLink(userId)),
  });
}
