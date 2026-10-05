// Константы и билдеры путей API.
// Единственное место, где захардкожены строки "/api/...".
import { isValidWikiSlug } from "@/lib/wikiSlug";

export const endpoints = {
  auth: {
    me: "/api/auth/me",
    login: "/api/auth/login",
    register: "/api/auth/register",
    logout: "/api/auth/logout",
    changePassword: "/api/auth/change-password",
    telegramVerify: "/api/auth/telegram-verify",
    telegramUnlink: "/api/auth/telegram-unlink",
  },
  recipes: {
    list: "/api/recipes",
    detail: (id: string) => `/api/recipes/${id}`,
  },
  menus: {
    list: "/api/menus",
    today: "/api/menus/today",
    suggest: (menuId: string) => `/api/menus/${menuId}/suggest`,
    vote: (menuId: string) => `/api/menus/${menuId}/vote`,
  },
  passwordReset: {
    request: "/api/auth/password-reset/request",
    confirm: "/api/auth/password-reset/confirm",
    validate: (token: string) =>
      `/api/auth/password-reset/validate?token=${encodeURIComponent(token)}`,
  },
  admin: {
    users: "/api/auth/admin/users",
    resetLink: (id: string) => `/api/auth/admin/users/${id}/reset-link`,
  },
  wiki: {
    health: "/api/wiki/health",
    notebooks: "/api/wiki/notebooks",
    notebookNotes: (notebookId: string) =>
      `/api/wiki/notebooks/${encodeURIComponent(notebookId)}/notes`,
    // slug содержит «/» — слэши остаются как есть, кодируются только сегменты.
    // Негодный slug (сегменты «.», «..», пустые) страница не запрашивает вовсе; здесь он на
    // всякий случай уходит одним закодированным сегментом — путь остаётся внутри
    // /api/wiki/notes/, и сервер ответит «Note not found».
    note: (slug: string) =>
      isValidWikiSlug(slug)
        ? `/api/wiki/notes/${slug.split("/").map(encodeURIComponent).join("/")}`
        : `/api/wiki/notes/%2F${encodeURIComponent(slug)}`,
    search: (params: { q?: string; project?: string; type?: string; tag?: string; limit?: number }) => {
      const query = new URLSearchParams();
      if (params.q) query.set("q", params.q);
      if (params.project) query.set("project", params.project);
      if (params.type) query.set("type", params.type);
      if (params.tag) query.set("tag", params.tag);
      if (params.limit) query.set("limit", String(params.limit));
      return `/api/wiki/search?${query.toString()}`;
    },
    recent: (limit: number) => `/api/wiki/recent?limit=${limit}`,
  },
} as const;
