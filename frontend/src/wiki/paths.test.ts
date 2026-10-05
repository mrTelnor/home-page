import { describe, expect, it } from "vitest";
import { notePath, notebookPath, searchPath, siteLoginUrl, wikiReturnPath } from "./paths";

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

describe("wikiReturnPath", () => {
  it("страница вики целиком: путь, запрос и якорь", () => {
    expect(wikiReturnPath({ pathname: "/n/a/b", search: "", hash: "" })).toBe("/n/a/b");
    expect(wikiReturnPath({ pathname: "/search", search: "?q=x&tag=k8s", hash: "#top" })).toBe(
      "/search?q=x&tag=k8s#top"
    );
  });

  it("своей страницы входа у вики нет: /login заменяется корнем", () => {
    expect(wikiReturnPath({ pathname: "/login", search: "", hash: "" })).toBe("/");
    expect(
      wikiReturnPath({ pathname: "/login", search: "?next=%2F%2Fevil.example", hash: "" })
    ).toBe("/");
  });
});

describe("siteLoginUrl", () => {
  const wiki = { protocol: "https:", host: "wiki.telnor.ru" };

  it("страница входа основного сайта с возвратом на страницу вики", () => {
    expect(siteLoginUrl("/n/a/b", wiki)).toBe(
      "https://telnor.ru/login?next=https%3A%2F%2Fwiki.telnor.ru%2Fn%2Fa%2Fb"
    );
    expect(siteLoginUrl("/", wiki)).toBe(
      "https://telnor.ru/login?next=https%3A%2F%2Fwiki.telnor.ru%2F"
    );
  });

  it("запрос страницы вики не смешивается с запросом страницы входа", () => {
    const url = new URL(siteLoginUrl("/search?q=a&tag=b#c", wiki) as string);
    expect(url.origin + url.pathname).toBe("https://telnor.ru/login");
    expect([...url.searchParams.keys()]).toEqual(["next"]);
    expect(url.searchParams.get("next")).toBe("https://wiki.telnor.ru/search?q=a&tag=b#c");
  });

  it("сохраняет схему и порт (локально: wiki.localhost)", () => {
    expect(siteLoginUrl("/n/a", { protocol: "http:", host: "wiki.localhost:5173" })).toBe(
      "http://localhost:5173/login?next=http%3A%2F%2Fwiki.localhost%3A5173%2Fn%2Fa"
    );
  });

  it("вне поддомена wiki. (VITE_WIKI=true) адрес сайта неизвестен — null", () => {
    expect(siteLoginUrl("/n/a", { protocol: "http:", host: "localhost:5173" })).toBeNull();
  });
});
