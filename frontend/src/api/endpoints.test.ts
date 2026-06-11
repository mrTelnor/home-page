import { describe, expect, it } from "vitest";
import { endpoints } from "./endpoints";

describe("endpoints", () => {
  it("содержит статические пути auth", () => {
    expect(endpoints.auth.me).toBe("/api/auth/me");
    expect(endpoints.auth.login).toBe("/api/auth/login");
    expect(endpoints.auth.register).toBe("/api/auth/register");
    expect(endpoints.auth.logout).toBe("/api/auth/logout");
    expect(endpoints.auth.changePassword).toBe("/api/auth/change-password");
    expect(endpoints.auth.telegramVerify).toBe("/api/auth/telegram-verify");
    expect(endpoints.auth.telegramUnlink).toBe("/api/auth/telegram-unlink");
  });

  it("строит пути рецептов по id", () => {
    expect(endpoints.recipes.list).toBe("/api/recipes");
    expect(endpoints.recipes.detail("abc")).toBe("/api/recipes/abc");
  });

  it("строит пути меню по id", () => {
    expect(endpoints.menus.list).toBe("/api/menus");
    expect(endpoints.menus.today).toBe("/api/menus/today");
    expect(endpoints.menus.suggest("m1")).toBe("/api/menus/m1/suggest");
    expect(endpoints.menus.vote("m1")).toBe("/api/menus/m1/vote");
  });
});
