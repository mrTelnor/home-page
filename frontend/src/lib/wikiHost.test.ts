import { afterEach, describe, expect, it, vi } from "vitest";
import { isWikiHost, mainSiteUrl } from "./wikiHost";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("isWikiHost", () => {
  it("хост wiki.<domain> — вики", () => {
    expect(isWikiHost("wiki.telnor.ru")).toBe(true);
    expect(isWikiHost("WIKI.example.org")).toBe(true);
    expect(isWikiHost("wiki.localhost")).toBe(true);
  });

  it("основной домен и прочие хосты — сайт рецептов", () => {
    expect(isWikiHost("telnor.ru")).toBe(false);
    expect(isWikiHost("localhost")).toBe(false);
    expect(isWikiHost("mywiki.telnor.ru")).toBe(false);
    expect(isWikiHost("")).toBe(false);
  });

  it("по умолчанию берёт хост страницы (в тестах — localhost)", () => {
    expect(isWikiHost()).toBe(false);
  });

  it("VITE_WIKI=true включает вики на любом хосте — для локальной разработки", () => {
    vi.stubEnv("VITE_WIKI", "true");
    expect(isWikiHost("localhost")).toBe(true);
  });
});

describe("mainSiteUrl", () => {
  it("срезает префикс wiki. и сохраняет протокол и порт", () => {
    expect(mainSiteUrl({ protocol: "https:", host: "wiki.telnor.ru" })).toBe("https://telnor.ru");
    expect(mainSiteUrl({ protocol: "http:", host: "wiki.localhost:5173" })).toBe(
      "http://localhost:5173"
    );
  });

  it("вне поддомена wiki. адрес сайта неизвестен", () => {
    expect(mainSiteUrl({ protocol: "http:", host: "localhost:5173" })).toBeNull();
  });
});
