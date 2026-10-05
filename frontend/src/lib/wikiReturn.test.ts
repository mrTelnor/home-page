import { describe, expect, it } from "vitest";
import { safeWikiReturnUrl } from "./wikiReturn";

const SITE = { protocol: "https:", host: "telnor.ru" };

describe("safeWikiReturnUrl", () => {
  it.each([
    ["https://wiki.telnor.ru", "https://wiki.telnor.ru/"],
    ["https://wiki.telnor.ru/", "https://wiki.telnor.ru/"],
    [
      "https://wiki.telnor.ru/n/moi-domashnii-sait/grabli",
      "https://wiki.telnor.ru/n/moi-domashnii-sait/grabli",
    ],
    ["https://wiki.telnor.ru/search?q=x&tag=k8s", "https://wiki.telnor.ru/search?q=x&tag=k8s"],
    ["https://wiki.telnor.ru/n/a#section", "https://wiki.telnor.ru/n/a#section"],
    ["HTTPS://WIKI.TELNOR.RU/n/a", "https://wiki.telnor.ru/n/a"],
    // Порт по умолчанию — тот же origin
    ["https://wiki.telnor.ru:443/n/a", "https://wiki.telnor.ru/n/a"],
    // Без слэшей после схемы URL-разбор (и браузер) видит тот же хост вики — уйти наружу нельзя
    ["https:wiki.telnor.ru/n/a", "https://wiki.telnor.ru/n/a"],
  ])("принимает адрес вики этого домена: %s", (raw, expected) => {
    expect(safeWikiReturnUrl(raw, SITE)).toBe(expected);
  });

  it.each([
    ["нет значения", null],
    ["нет значения (undefined)", undefined],
    ["пустая строка", ""],
    ["чужой хост", "https://evil.example/"],
    ["чужой хост с путём как у вики", "https://evil.example/wiki.telnor.ru/n/a"],
    ["хост вики в запросе чужого адреса", "https://evil.example/?https://wiki.telnor.ru/"],
    ["хост вики как префикс чужого", "https://wiki.telnor.ru.evil.example/"],
    ["хост вики как суффикс чужого", "https://evilwiki.telnor.ru/"],
    ["лишний поддомен", "https://x.wiki.telnor.ru/"],
    ["сам сайт, а не вики", "https://telnor.ru/n/a"],
    ["другой домен с поддоменом wiki", "https://wiki.telnor.com/"],
    ["точка в конце хоста", "https://wiki.telnor.ru./"],
    ["другой порт", "https://wiki.telnor.ru:8443/"],
    ["другая схема (http)", "http://wiki.telnor.ru/"],
    ["другая схема (ftp)", "ftp://wiki.telnor.ru/"],
    ["без схемы: //host", "//wiki.telnor.ru/n/a"],
    ["без схемы: //чужой", "//evil.example"],
    ["путь без хоста", "/n/a"],
    ["хост без схемы", "wiki.telnor.ru/n/a"],
    ["обратные слэши вместо //", "https:\\\\wiki.telnor.ru/"],
    ["обратный слэш перед @", "https://wiki.telnor.ru\\@evil.example/"],
    ["обратный слэш в пути", "https://wiki.telnor.ru/\\evil.example"],
    ["обратные слэши без схемы", "\\\\evil.example"],
    ["javascript:", "javascript:alert(1)"],
    ["javascript: с хостом вики", "javascript://wiki.telnor.ru/%0aalert(1)"],
    ["data:", "data:text/html,<script>alert(1)</script>"],
    ["userinfo: вики как логин чужого хоста", "https://wiki.telnor.ru@evil.example/"],
    ["userinfo: логин и пароль", "https://wiki.telnor.ru:pass@evil.example/"],
    ["userinfo перед хостом вики", "https://evil.example@wiki.telnor.ru/"],
    ["userinfo с паролем перед хостом вики", "https://user:pass@wiki.telnor.ru/"],
    ["табуляция в хосте", "https://wiki.telnor.ru\t.evil.example/"],
    ["перевод строки в адресе", "https://wiki.telnor.ru/\n/evil.example"],
    ["возврат каретки в адресе", "https://wiki.telnor.ru/\r/evil.example"],
    ["пробел в начале", " https://wiki.telnor.ru/"],
    ["табуляция в схеме", "ht\ttps://wiki.telnor.ru/"],
    ["нулевой байт", "https://wiki.telnor.ru/\u0000"],
    ["путь, начинающийся с //", "https://wiki.telnor.ru//evil.example"],
    ["кодированная точка в хосте", "https://wiki%2Etelnor.ru.evil.example/"],
  ])("отсекает: %s", (_name, raw) => {
    expect(safeWikiReturnUrl(raw, SITE)).toBeNull();
  });

  it("хост и схема берутся от сайта, на котором открыта страница входа", () => {
    const local = { protocol: "http:", host: "localhost:5173" };
    expect(safeWikiReturnUrl("http://wiki.localhost:5173/n/a", local)).toBe(
      "http://wiki.localhost:5173/n/a"
    );
    // Тот же хост, другой порт
    expect(safeWikiReturnUrl("http://wiki.localhost:3000/n/a", local)).toBeNull();
    expect(safeWikiReturnUrl("http://wiki.localhost/n/a", local)).toBeNull();
    // Вики чужого домена
    expect(safeWikiReturnUrl("https://wiki.telnor.ru/n/a", local)).toBeNull();
    // Со страницы по https на http не возвращаем
    expect(safeWikiReturnUrl("http://wiki.telnor.ru/n/a", SITE)).toBeNull();
  });

  it("страница открыта не по http(s) — возврата нет", () => {
    expect(safeWikiReturnUrl("file://wiki./n/a", { protocol: "file:", host: "" })).toBeNull();
  });

  it("результат собран от своего origin: из значения взяты только путь, запрос и якорь", () => {
    const result = safeWikiReturnUrl("https://wiki.telnor.ru/n/a%20b?q=%2F%2Fevil.example#x", SITE);
    expect(result).toBe("https://wiki.telnor.ru/n/a%20b?q=%2F%2Fevil.example#x");
    expect(new URL(result as string).origin).toBe("https://wiki.telnor.ru");
  });

  it("по умолчанию сверяется с адресом текущей страницы (в тестах — http://localhost:3000)", () => {
    expect(safeWikiReturnUrl(`http://wiki.${window.location.host}/n/a`)).toBe(
      `http://wiki.${window.location.host}/n/a`
    );
    expect(safeWikiReturnUrl("https://wiki.telnor.ru/n/a")).toBeNull();
  });
});
