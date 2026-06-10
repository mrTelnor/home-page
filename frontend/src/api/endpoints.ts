// Константы и билдеры путей API.
// Единственное место, где захардкожены строки "/api/...".

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
} as const;
