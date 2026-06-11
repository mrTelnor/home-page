import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, screen, waitFor } from "@testing-library/react";
import {
  useCreateRecipe,
  useDeleteRecipe,
  useRecipe,
  useRecipesList,
  useUpdateRecipe,
} from "./useRecipes";
import { createWrapper, makeRecipe, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useRecipesList", () => {
  it("загружает список рецептов", async () => {
    fetchMock.mockResolvedValueOnce(mockResponse({ body: [makeRecipe()] }));
    const { Wrapper } = createWrapper();

    const { result } = renderHook(() => useRecipesList(), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([makeRecipe()]);
  });

  it("отдаёт ошибку при падении сервера", async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse({ ok: false, status: 500, body: { detail: "Server error" } })
    );
    const { Wrapper } = createWrapper();

    const { result } = renderHook(() => useRecipesList(), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe("useRecipe", () => {
  it("загружает рецепт по id", async () => {
    const recipe = makeRecipe();
    fetchMock.mockResolvedValueOnce(mockResponse({ body: recipe }));
    const { Wrapper } = createWrapper();

    const { result } = renderHook(() => useRecipe("recipe-1"), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(recipe);
    expect((fetchMock.mock.calls[0] as [string])[0]).toContain("/api/recipes/recipe-1");
  });

  it("не делает запрос при пустом id", () => {
    const { Wrapper } = createWrapper();

    renderHook(() => useRecipe(""), { wrapper: Wrapper });

    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("useCreateRecipe", () => {
  it("после создания инвалидирует список и ведёт на страницу рецепта", async () => {
    const created = makeRecipe({ id: "recipe-7" });
    fetchMock.mockResolvedValueOnce(mockResponse({ body: created }));
    const { Wrapper, queryClient } = createWrapper({ route: "/recipes/new" });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useCreateRecipe(), { wrapper: Wrapper });
    result.current.mutate({
      title: "Борщ",
      servings: 4,
      ingredients: [{ name: "Свёкла", amount: "2", unit: "шт" }],
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["recipes"] });
    expect(screen.getByTestId("location")).toHaveTextContent("/recipes/recipe-7");
  });
});

describe("useUpdateRecipe", () => {
  it("шлёт PUT, инвалидирует кеши и ведёт на рецепт", async () => {
    fetchMock.mockResolvedValueOnce(mockResponse({ body: makeRecipe() }));
    const { Wrapper, queryClient } = createWrapper({ route: "/recipes/recipe-1/edit" });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useUpdateRecipe("recipe-1"), { wrapper: Wrapper });
    result.current.mutate({ title: "Новый борщ" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/recipes/recipe-1");
    expect(options.method).toBe("PUT");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["recipes"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["recipes", "recipe-1"] });
    expect(screen.getByTestId("location")).toHaveTextContent("/recipes/recipe-1");
  });
});

describe("useDeleteRecipe", () => {
  it("шлёт DELETE и ведёт на список рецептов", async () => {
    fetchMock.mockResolvedValueOnce(mockResponse({ status: 204, body: null }));
    const { Wrapper, queryClient } = createWrapper({ route: "/recipes/recipe-1" });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useDeleteRecipe(), { wrapper: Wrapper });
    result.current.mutate("recipe-1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/recipes/recipe-1");
    expect(options.method).toBe("DELETE");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["recipes"] });
    expect(screen.getByTestId("location")).toHaveTextContent("/recipes");
  });
});
