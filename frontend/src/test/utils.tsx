/* eslint-disable react-refresh/only-export-components -- тестовые хелперы, не участвуют в HMR */
// Общие хелперы для тестов: провайдеры, мок fetch-ответов, фикстуры данных.
import { type ReactNode } from "react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type Menu, type MenuRecipe, type Recipe, type User } from "@/api/types";

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

/** Показывает текущий путь — чтобы проверять navigate() в хуках и страницах. */
export function LocationDisplay() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
}

interface WrapperOptions {
  route?: string;
  queryClient?: QueryClient;
}

/** Обёртка QueryClientProvider + MemoryRouter для renderHook/render. */
export function createWrapper({ route = "/", queryClient }: WrapperOptions = {}) {
  const client = queryClient ?? createQueryClient();
  function Wrapper({ children }: Readonly<{ children: ReactNode }>) {
    return (
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[route]}>
          {children}
          <LocationDisplay />
        </MemoryRouter>
      </QueryClientProvider>
    );
  }
  return { Wrapper, queryClient: client };
}

interface MockResponseInit {
  ok?: boolean;
  status?: number;
  statusText?: string;
  body?: unknown;
}

/** Минимальный Response-совместимый объект для мока fetch. */
export function mockResponse({
  ok = true,
  status = 200,
  statusText = "OK",
  body = {},
}: MockResponseInit = {}) {
  return {
    ok,
    status,
    statusText,
    json: () => Promise.resolve(body),
  };
}

export function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: "user-1",
    username: "nikita",
    role: "user",
    created_at: "2026-01-01T00:00:00Z",
    tg_id: null,
    first_name: null,
    birthday: null,
    is_volkov: false,
    gender: null,
    email: null,
    ...overrides,
  };
}

export function makeRecipe(overrides: Partial<Recipe> = {}): Recipe {
  return {
    id: "recipe-1",
    title: "Борщ",
    description: "Варить час.",
    servings: 4,
    author_id: "user-1",
    ingredients: [{ id: "ing-1", name: "Свёкла", amount: "2", unit: "шт" }],
    glyph_kind: null,
    glyph_color: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function makeMenuRecipe(overrides: Partial<MenuRecipe> = {}): MenuRecipe {
  return {
    id: "mr-1",
    recipe_id: "recipe-1",
    title: "Борщ",
    source: "random",
    added_by: null,
    votes_count: 0,
    voters: [],
    ...overrides,
  };
}

export function makeMenu(overrides: Partial<Menu> = {}): Menu {
  return {
    id: "menu-1",
    date: "2026-06-11",
    status: "voting",
    winner_recipe_id: null,
    recipes: [makeMenuRecipe()],
    created_at: "2026-06-11T08:00:00Z",
    user_voted_recipe_id: null,
    total_votes: 0,
    ...overrides,
  };
}
