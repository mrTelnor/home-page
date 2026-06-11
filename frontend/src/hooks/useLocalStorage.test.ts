import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useLocalStorage } from "./useLocalStorage";

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useLocalStorage", () => {
  it("берёт значение по умолчанию, если в хранилище пусто", () => {
    const { result } = renderHook(() => useLocalStorage("key", 42));

    expect(result.current[0]).toBe(42);
    expect(localStorage.getItem("key")).toBe("42");
  });

  it("поддерживает ленивый дефолт-функцию", () => {
    const { result } = renderHook(() => useLocalStorage("key", () => "lazy"));

    expect(result.current[0]).toBe("lazy");
  });

  it("читает существующее JSON-значение", () => {
    localStorage.setItem("key", JSON.stringify({ a: 1 }));

    const { result } = renderHook(() => useLocalStorage("key", { a: 0 }));

    expect(result.current[0]).toEqual({ a: 1 });
  });

  it("при битом JSON откатывается на дефолт", () => {
    localStorage.setItem("key", "{не json");

    const { result } = renderHook(() => useLocalStorage("key", "default"));

    expect(result.current[0]).toBe("default");
  });

  it("записывает значение при изменении (включая функциональный апдейт)", () => {
    const { result } = renderHook(() => useLocalStorage("counter", 1));

    act(() => {
      result.current[1]((v) => v + 1);
    });

    expect(result.current[0]).toBe(2);
    expect(localStorage.getItem("counter")).toBe("2");
  });

  it("использует кастомные serialize/deserialize", () => {
    localStorage.setItem("theme", "dark");

    const { result } = renderHook(() =>
      useLocalStorage<string>("theme", "light", {
        serialize: (v) => v,
        deserialize: (raw) => (raw === "light" || raw === "dark" ? raw : undefined),
      })
    );

    expect(result.current[0]).toBe("dark");

    act(() => {
      result.current[1]("light");
    });

    expect(localStorage.getItem("theme")).toBe("light");
  });

  it("берёт дефолт, если deserialize вернул undefined", () => {
    localStorage.setItem("theme", "мусор");

    const { result } = renderHook(() =>
      useLocalStorage<string>("theme", "light", {
        serialize: (v) => v,
        deserialize: (raw) => (raw === "dark" ? raw : undefined),
      })
    );

    expect(result.current[0]).toBe("light");
  });

  it("не падает, если localStorage.setItem бросает (private mode)", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });

    const { result } = renderHook(() => useLocalStorage("key", "v"));

    act(() => {
      result.current[1]("новое");
    });

    expect(result.current[0]).toBe("новое");
  });

  it("не падает, если localStorage.getItem бросает", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("SecurityError");
    });

    const { result } = renderHook(() => useLocalStorage("key", "fallback"));

    expect(result.current[0]).toBe("fallback");
  });
});
