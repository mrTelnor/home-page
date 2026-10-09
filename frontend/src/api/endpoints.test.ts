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

  it("строит пути вики", () => {
    expect(endpoints.wiki.health).toBe("/api/wiki/health");
    expect(endpoints.wiki.notebooks).toBe("/api/wiki/notebooks");
    expect(endpoints.wiki.notebookNotes("nb-1")).toBe("/api/wiki/notebooks/nb-1/notes");
    expect(endpoints.wiki.recent(20)).toBe("/api/wiki/recent?limit=20");
  });

  it("slug заметки вики уходит со слэшами, сегменты кодируются", () => {
    expect(endpoints.wiki.note("moi-domashnii-sait/grabli")).toBe(
      "/api/wiki/notes/moi-domashnii-sait/grabli"
    );
    expect(endpoints.wiki.note("a b/c?d#e")).toBe("/api/wiki/notes/a%20b/c%3Fd%23e");
  });

  it("поиск вики: только заданные параметры", () => {
    expect(endpoints.wiki.search({})).toBe("/api/wiki/search?");
    expect(
      endpoints.wiki.search({
        q: "a b",
        project: "home-page",
        type: "runbook",
        tag: "k8s",
        limit: 50,
      })
    ).toBe("/api/wiki/search?q=a+b&project=home-page&type=runbook&tag=k8s&limit=50");
  });
});
