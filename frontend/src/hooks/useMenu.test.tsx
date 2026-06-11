import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import {
  useAllRecipes,
  useCancelVote,
  useMenuHistory,
  useSuggestRecipe,
  useTodayMenu,
  useVote,
} from "./useMenu";
import { createWrapper, makeMenu, makeRecipe, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useTodayMenu", () => {
  it("возвращает меню дня", async () => {
    const menu = makeMenu();
    fetchMock.mockResolvedValueOnce(mockResponse({ body: menu }));
    const { Wrapper } = createWrapper();

    const { result } = renderHook(() => useTodayMenu(), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(menu);
    expect((fetchMock.mock.calls[0] as [string])[0]).toContain("/api/menus/today");
  });

  it("возвращает null, если меню ещё нет (404)", async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse({ ok: false, status: 404, body: { detail: "Not found" } })
    );
    const { Wrapper } = createWrapper();

    const { result } = renderHook(() => useTodayMenu(), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBeNull();
  });
});

describe("useMenuHistory", () => {
  it("загружает список меню", async () => {
    const menus = [makeMenu(), makeMenu({ id: "menu-2" })];
    fetchMock.mockResolvedValueOnce(mockResponse({ body: menus }));
    const { Wrapper } = createWrapper();

    const { result } = renderHook(() => useMenuHistory(), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(2);
    expect((fetchMock.mock.calls[0] as [string])[0]).toContain("/api/menus");
  });
});

describe("useAllRecipes", () => {
  it("загружает все рецепты", async () => {
    fetchMock.mockResolvedValueOnce(mockResponse({ body: [makeRecipe()] }));
    const { Wrapper } = createWrapper();

    const { result } = renderHook(() => useAllRecipes(), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([makeRecipe()]);
  });
});

describe("useSuggestRecipe", () => {
  it("шлёт recipe_id и инвалидирует меню дня", async () => {
    fetchMock.mockResolvedValueOnce(mockResponse({ body: {} }));
    const { Wrapper, queryClient } = createWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useSuggestRecipe(), { wrapper: Wrapper });
    result.current.mutate({ menuId: "menu-1", recipeId: "recipe-9" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/menus/menu-1/suggest");
    expect(options.body).toBe(JSON.stringify({ recipe_id: "recipe-9" }));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["menu", "today"] });
  });
});

describe("useVote", () => {
  it("голосует и инвалидирует меню дня", async () => {
    fetchMock.mockResolvedValueOnce(mockResponse({ body: {} }));
    const { Wrapper, queryClient } = createWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useVote(), { wrapper: Wrapper });
    result.current.mutate({ menuId: "menu-1", recipeId: "recipe-2" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/menus/menu-1/vote");
    expect(options.method).toBe("POST");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["menu", "today"] });
  });

  it("отдаёт ошибку при отказе сервера", async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse({ ok: false, status: 409, body: { detail: "Already voted" } })
    );
    const { Wrapper } = createWrapper();

    const { result } = renderHook(() => useVote(), { wrapper: Wrapper });
    result.current.mutate({ menuId: "menu-1", recipeId: "recipe-2" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect((result.current.error as Error).message).toBe("Already voted");
  });
});

describe("useCancelVote", () => {
  it("шлёт DELETE и инвалидирует меню дня", async () => {
    fetchMock.mockResolvedValueOnce(mockResponse({ status: 204, body: null }));
    const { Wrapper, queryClient } = createWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useCancelVote(), { wrapper: Wrapper });
    result.current.mutate({ menuId: "menu-1" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/menus/menu-1/vote");
    expect(options.method).toBe("DELETE");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["menu", "today"] });
  });
});
