import { describe, expect, it } from "vitest";
import { loginPath, notePath, notebookPath, safeNextPath, searchPath } from "./paths";

describe("пути вики", () => {
  it("slug заметки сохраняет слэши, сегменты кодируются", () => {
    expect(notePath("moi-domashnii-sait/grabli")).toBe("/n/moi-domashnii-sait/grabli");
    expect(notePath("a b/c?d")).toBe("/n/a%20b/c%3Fd");
  });

  it("путь блокнота — по id", () => {
    expect(notebookPath("11111111-2222-3333-4444-555555555555")).toBe(
      "/b/11111111-2222-3333-4444-555555555555"
    );
  });

  it("поиск: в адрес попадают только заданные параметры", () => {
    expect(searchPath()).toBe("/search");
    expect(searchPath({ q: "", tag: "" })).toBe("/search");
    expect(searchPath({ q: "traefik", type: "runbook" })).toBe("/search?q=traefik&type=runbook");
  });
});

describe("safeNextPath", () => {
  it("пропускает путь внутри вики", () => {
    expect(safeNextPath("/n/a/b")).toBe("/n/a/b");
    expect(safeNextPath("/search?q=x")).toBe("/search?q=x");
  });

  it.each([
    null,
    undefined,
    "",
    "https://evil.example",
    "//evil.example",
    "/\\evil.example",
    "n/a",
    "/login",
    "/login?next=/",
  ])("не пропускает %s", (raw) => {
    expect(safeNextPath(raw)).toBe("/");
  });
});

describe("loginPath", () => {
  it("добавляет возврат, кроме корня", () => {
    expect(loginPath("/")).toBe("/login");
    expect(loginPath("/n/a/b")).toBe("/login?next=%2Fn%2Fa%2Fb");
  });
});
