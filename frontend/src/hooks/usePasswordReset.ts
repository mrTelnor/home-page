import { useMutation } from "@tanstack/react-query";
import { api } from "@/api/client";
import { endpoints } from "@/api/endpoints";

export type ResetChannel = "telegram" | "email";

export interface RequestResetResult {
  status: "sent" | "choose" | "no_channels";
  channels?: ResetChannel[];
}

export function useRequestReset() {
  return useMutation({
    mutationFn: (data: { identifier: string; channel?: ResetChannel }) =>
      api.post<RequestResetResult>(endpoints.passwordReset.request, data),
  });
}

export function useConfirmReset() {
  return useMutation({
    mutationFn: (data: { token: string; new_password: string }) =>
      api.post<{ status: string }>(endpoints.passwordReset.confirm, data),
  });
}
