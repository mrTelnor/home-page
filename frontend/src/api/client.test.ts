import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./client";

const API_URL = import.meta.env.VITE_API_URL || "https://api.telnor.ru";

interface MockResponseInit {
  ok?: boolean;
  status?: number;
  statusText?: string;
  body?: unknown;
  jsonFails?: boolean;
}

function mockResponse({
  ok = true,
  status = 200,
  statusText = "OK",
  body = {},
  jsonFails = false,
}: MockResponseInit = {}) {
  return {
    ok,
    status,
    statusText,
    json: jsonFails ? () => Promise.reject(new Error("invalid json")) : () => Promise.resolve(body),
  };
}

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api.get", () => {
  it("парсит JSON успешного ответа и зовёт правильный URL", async () => {
    const payload = { id: 1, title: "Борщ" };
    fetchMock.mockResolvedValueOnce(mockResponse({ body: payload }));

    const result = await api.get<typeof payload>("/recipes/1");

    expect(result).toEqual(payload);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_URL}/recipes/1`,
      expect.objectContaining({ credentials: "include" })
    );
  });

  it("бросает ApiError с правильным status и detail на не-2xx", async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse({ ok: false, status: 404, body: { detail: "Recipe not found" } })
    );

    const error = await api.get("/recipes/999").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(404);
    expect((error as ApiError).message).toBe("Recipe not found");
  });

  it("использует statusText, если тело ошибки не JSON", async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse({ ok: false, status: 500, statusText: "Internal Server Error", jsonFails: true })
    );

    const error = await api.get("/recipes").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(500);
    expect((error as ApiError).message).toBe("Internal Server Error");
  });
});

describe("api.post", () => {
  it("шлёт JSON-тело, Content-Type application/json и credentials include", async () => {
    fetchMock.mockResolvedValueOnce(mockResponse({ body: { id: 2 } }));
    const data = { title: "Окрошка", servings: 4 };

    await api.post("/recipes", data);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_URL}/recipes`);
    expect(options.method).toBe("POST");
    expect(options.credentials).toBe("include");
    expect(options.headers).toMatchObject({ "Content-Type": "application/json" });
    expect(options.body).toBe(JSON.stringify(data));
  });

  it("не шлёт body, если данных нет", async () => {
    fetchMock.mockResolvedValueOnce(mockResponse({ body: {} }));

    await api.post("/auth/logout");

    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(options.body).toBeUndefined();
  });
});

describe("api.del", () => {
  it("возвращает undefined для 204 No Content", async () => {
    fetchMock.mockResolvedValueOnce(mockResponse({ status: 204, body: null }));

    const result = await api.del("/recipes/1");

    expect(result).toBeUndefined();
    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(options.method).toBe("DELETE");
  });
});
