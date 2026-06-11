import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, screen, waitFor } from "@testing-library/react";
import { useLogin, useLogout, useMe, useRegister } from "./useAuth";
import { useAuthStore } from "@/store/auth";
import { createWrapper, makeUser, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  useAuthStore.setState({ user: null });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useMe", () => {
  it("кладёт пользователя в стор при успехе", async () => {
    const user = makeUser();
    fetchMock.mockResolvedValueOnce(mockResponse({ body: user }));
    const { Wrapper } = createWrapper();

    const { result } = renderHook(() => useMe(), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(user);
    expect(useAuthStore.getState().user).toEqual(user);
  });

  it("очищает стор и возвращает null при 401", async () => {
    useAuthStore.setState({ user: makeUser() });
    fetchMock.mockResolvedValueOnce(
      mockResponse({ ok: false, status: 401, body: { detail: "Not authenticated" } })
    );
    const { Wrapper } = createWrapper();

    const { result } = renderHook(() => useMe(), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
  });
});

describe("useLogin", () => {
  it("после успеха инвалидирует me и ведёт на главную", async () => {
    fetchMock.mockResolvedValue(mockResponse({ body: makeUser() }));
    const { Wrapper, queryClient } = createWrapper({ route: "/login" });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useLogin(), { wrapper: Wrapper });
    result.current.mutate({ username: "nikita", password: "secret123" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["me"] });
    expect(screen.getByTestId("location")).toHaveTextContent("/");

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/auth/login");
    expect(options.body).toBe(JSON.stringify({ username: "nikita", password: "secret123" }));
  });

  it("при ошибке остаётся на месте и отдаёт error", async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse({ ok: false, status: 401, body: { detail: "Bad credentials" } })
    );
    const { Wrapper } = createWrapper({ route: "/login" });

    const { result } = renderHook(() => useLogin(), { wrapper: Wrapper });
    result.current.mutate({ username: "nikita", password: "wrong" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(screen.getByTestId("location")).toHaveTextContent("/login");
  });
});

describe("useRegister", () => {
  it("после успеха ведёт на /login", async () => {
    fetchMock.mockResolvedValueOnce(mockResponse({ body: makeUser() }));
    const { Wrapper } = createWrapper({ route: "/register" });

    const { result } = renderHook(() => useRegister(), { wrapper: Wrapper });
    result.current.mutate({ username: "new", password: "secret123", invite_code: "code" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(screen.getByTestId("location")).toHaveTextContent("/login");
  });
});

describe("useLogout", () => {
  it("чистит стор, кеш и ведёт на /login", async () => {
    useAuthStore.setState({ user: makeUser() });
    fetchMock.mockResolvedValueOnce(mockResponse({ status: 204, body: null }));
    const { Wrapper, queryClient } = createWrapper({ route: "/profile" });
    const clearSpy = vi.spyOn(queryClient, "clear");

    const { result } = renderHook(() => useLogout(), { wrapper: Wrapper });
    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(useAuthStore.getState().user).toBeNull();
    expect(clearSpy).toHaveBeenCalled();
    expect(screen.getByTestId("location")).toHaveTextContent("/login");
  });
});
