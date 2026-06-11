import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import {
  useChangePassword,
  useTelegramUnlink,
  useTelegramVerify,
  useUpdateProfile,
  type TelegramAuthData,
} from "./useProfile";
import { createWrapper, makeUser, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const tgData: TelegramAuthData = {
  id: 123,
  first_name: "Никита",
  auth_date: 1700000000,
  hash: "abc",
};

describe("useTelegramVerify", () => {
  it("шлёт данные Telegram и инвалидирует me", async () => {
    fetchMock.mockResolvedValueOnce(mockResponse({ body: makeUser({ tg_id: 123 }) }));
    const { Wrapper, queryClient } = createWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useTelegramVerify(), { wrapper: Wrapper });
    result.current.mutate(tgData);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/auth/telegram-verify");
    expect(options.body).toBe(JSON.stringify(tgData));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["me"] });
  });
});

describe("useTelegramUnlink", () => {
  it("шлёт POST на unlink и инвалидирует me", async () => {
    fetchMock.mockResolvedValueOnce(mockResponse({ body: makeUser() }));
    const { Wrapper, queryClient } = createWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useTelegramUnlink(), { wrapper: Wrapper });
    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect((fetchMock.mock.calls[0] as [string])[0]).toContain("/api/auth/telegram-unlink");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["me"] });
  });
});

describe("useChangePassword", () => {
  it("шлёт старый и новый пароли", async () => {
    fetchMock.mockResolvedValueOnce(mockResponse({ body: {} }));
    const { Wrapper } = createWrapper();

    const { result } = renderHook(() => useChangePassword(), { wrapper: Wrapper });
    result.current.mutate({ old_password: "old12345", new_password: "new12345" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/auth/change-password");
    expect(options.body).toBe(
      JSON.stringify({ old_password: "old12345", new_password: "new12345" })
    );
  });

  it("отдаёт ошибку при неверном текущем пароле", async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse({ ok: false, status: 401, body: { detail: "Wrong password" } })
    );
    const { Wrapper } = createWrapper();

    const { result } = renderHook(() => useChangePassword(), { wrapper: Wrapper });
    result.current.mutate({ old_password: "bad", new_password: "new12345" });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe("useUpdateProfile", () => {
  it("шлёт PATCH на /api/auth/me и инвалидирует me", async () => {
    fetchMock.mockResolvedValueOnce(mockResponse({ body: makeUser({ first_name: "Ник" }) }));
    const { Wrapper, queryClient } = createWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useUpdateProfile(), { wrapper: Wrapper });
    result.current.mutate({ first_name: "Ник", is_volkov: true });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/auth/me");
    expect(options.method).toBe("PATCH");
    expect(options.body).toBe(JSON.stringify({ first_name: "Ник", is_volkov: true }));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["me"] });
  });
});
