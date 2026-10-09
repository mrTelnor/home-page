// QA: попытки обойти проверку адреса возврата на вики (задача трекера 12, доработка шага 5).
// Свойство одно: результат либо null, либо адрес ровно на origin вики этого сайта —
// какой бы хитрой ни была строка в `?next=`.
import { describe, expect, it } from "vitest";
import { siteLoginUrl, wikiReturnPath } from "@/wiki/paths";
import { safeWikiReturnUrl } from "./wikiReturn";

const SITE = { protocol: "https:", host: "telnor.ru" };
const WIKI_LOC = { protocol: "https:", host: "wiki.telnor.ru" };
const WIKI = "https://wiki.telnor.ru";

/** Адрес остаётся на вики, как бы его ни разбирал браузер: и сам по себе, и от адреса сайта. */
function expectOnWiki(result: string) {
  expect(result.startsWith(`${WIKI}/`)).toBe(true);
  for (const parsed of [new URL(result), new URL(result, "https://telnor.ru/login")]) {
    expect(parsed.origin).toBe(WIKI);
    expect(parsed.username).toBe("");
    expect(parsed.password).toBe("");
    // Роутер вики не должен получить путь, похожий на адрес с хостом
    expect(parsed.pathname.startsWith("//")).toBe(false);
  }
  // Повторный разбор ничего не меняет: браузер перейдёт ровно по этой строке
  expect(new URL(result).href).toBe(result);
}

const LONG = "a".repeat(100_000);

/** Значения, которые обязаны быть отсечены. */
const MUST_REJECT: [string, string][] = [
  // Хост: IDN и punycode чужих доменов, похожих на свой
  ["кириллическая «і» в wiki (омоглиф)", "https://wіki.telnor.ru/"],
  ["кириллическая «е» в telnor (омоглиф)", "https://wiki.tеlnor.ru/"],
  ["punycode чужого домена", "https://xn--wki-qmc.telnor.ru/"],
  ["punycode как поддомен чужого", "https://wiki.telnor.ru.xn--e1afmkfd.xn--p1ai/"],
  ["кириллический домен", "https://wiki.телнор.рф/"],
  ["точка в конце хоста", "https://wiki.telnor.ru./n/a"],
  ["две точки в конце", "https://wiki.telnor.ru../n/a"],
  ["%-кодированная точка + чужой суффикс", "https://wiki.telnor.ru%2eevil.example/"],
  ["%-кодированный слэш в хосте", "https://wiki.telnor.ru%2fevil.example/"],
  ["%-кодированная @ в хосте", "https://wiki.telnor.ru%40evil.example/"],
  ["%-кодированный # в хосте", "https://wiki.telnor.ru%23.evil.example/"],
  ["%-кодированный ? в хосте", "https://wiki.telnor.ru%3f.evil.example/"],
  ["%-кодированный : в хосте", "https://wiki.telnor.ru%3a443.evil.example/"],
  ["двойное кодирование точки", "https://wiki.telnor.ru%252eevil.example/"],
  ["нулевой байт в хосте (%00)", "https://wiki.telnor.ru%00.evil.example/"],
  // Числовые формы хоста и IPv6
  ["IPv4", "https://127.0.0.1/"],
  ["IPv4 одним числом", "https://2130706433/"],
  ["IPv4 шестнадцатеричный", "https://0x7f.0.0.1/"],
  ["IPv4 восьмеричный", "https://0177.0.0.1/"],
  ["IPv6", "https://[::1]/"],
  ["IPv6 с хостом вики в пути", "https://[::1]/wiki.telnor.ru/"],
  ["IPv6, отображающий IPv4", "https://[::ffff:127.0.0.1]/"],
  ["wiki. + IPv4", "https://wiki.127.0.0.1/"],
  // userinfo
  ["несколько @: вики первой", "https://wiki.telnor.ru@wiki.telnor.ru@evil.example/"],
  ["несколько @: вики последней", "https://evil.example@evil.example@wiki.telnor.ru/"],
  ["пустой логин с паролем", "https://:pass@wiki.telnor.ru/"],
  ["логин без пароля", "https://user@wiki.telnor.ru/"],
  ["%-кодированная @ в логине", "https://a%40b@wiki.telnor.ru/"],
  ["@ после пути чужого хоста", "https://evil.example/@wiki.telnor.ru/"],
  ["# перед @", "https://evil.example#@wiki.telnor.ru/"],
  ["? перед @", "https://evil.example?@wiki.telnor.ru/"],
  // Схема и слэши
  ["http вместо https в смешанном регистре", "HtTp://wiki.telnor.ru/"],
  ["схема без слэшей, чужой хост", "https:evil.example/"],
  ["один слэш, чужой хост", "https:/evil.example/"],
  ["три слэша, чужой хост", "https:///evil.example/"],
  ["blob:", "blob:https://wiki.telnor.ru/uuid"],
  ["view-source:", "view-source:https://wiki.telnor.ru/"],
  ["filesystem:", "filesystem:https://wiki.telnor.ru/temporary/x"],
  ["ws:", "wss://wiki.telnor.ru/"],
  ["схема с пробелом", "https ://wiki.telnor.ru/"],
  ["только схема", "https:"],
  ["схема и слэши", "https://"],
  // Порт
  ["порт 80 при https", "https://wiki.telnor.ru:80/"],
  ["порт 0", "https://wiki.telnor.ru:0/"],
  ["порт не число", "https://wiki.telnor.ru:abc/"],
  ["порт больше 65535", "https://wiki.telnor.ru:99999/"],
  // Путь, который после разбора начинается с //
  ["/..// → //", "https://wiki.telnor.ru/..//evil.example"],
  ["/.// → //", "https://wiki.telnor.ru/.//evil.example"],
  ["/a/..// → //", "https://wiki.telnor.ru/a/..//evil.example"],
  ["/%2e%2e// → //", "https://wiki.telnor.ru/%2e%2e//evil.example"],
  ["/%2E// → //", "https://wiki.telnor.ru/%2E//evil.example"],
  ["обратный слэш в пути", "https://wiki.telnor.ru/\\evil.example"],
  ["обратный слэш после /..", "https://wiki.telnor.ru/..\\/evil.example"],
  ["обратный слэш в запросе", "https://wiki.telnor.ru/?\\evil.example"],
  // Пробельные и управляющие символы, которые браузер выбрасывает или обрезает
  ["пробел в конце", "https://wiki.telnor.ru/ "],
  ["табуляция внутри //", "https:/\t/evil.example/"],
  ["перевод строки в хосте", "https://wiki.telnor.ru\n.evil.example/"],
  ["DEL (0x7f)", "https://wiki.telnor.ru/\u007f"],
  ["вертикальная табуляция", "https://wiki.telnor.ru/\u000b/evil.example"],
  // Очень длинные
  ["очень длинный чужой хост", `https://${LONG}.evil.example/`],
  ["очень длинный мусор", LONG],
  // Вложенный адрес
  ["адрес сайта, а в его next — вики", "https://telnor.ru/login?next=https://wiki.telnor.ru/"],
  ["закодированный целиком адрес вики", "https%3A%2F%2Fwiki.telnor.ru%2F"],
];

/** Значения, которые можно принять — но только оставаясь на origin вики. */
const MAY_ACCEPT: [string, string][] = [
  ["смешанный регистр схемы и хоста", "hTtPs://WiKi.TeLnOr.Ru/n/a"],
  ["полноширинные буквы хоста (IDNA приводит к ASCII)", "https://ｗｉｋｉ.telnor.ru/n/a"],
  ["идеографическая точка в хосте", "https://wiki。telnor.ru/n/a"],
  ["%-кодированные буквы хоста", "https://%77iki.telnor.ru/n/a"],
  ["%-кодированная точка внутри своего хоста", "https://wiki%2Etelnor.ru/n/a"],
  ["без слэшей после схемы", "https:wiki.telnor.ru/n/a"],
  ["один слэш после схемы", "https:/wiki.telnor.ru/n/a"],
  ["три слэша после схемы", "https:///wiki.telnor.ru/n/a"],
  ["много слэшей после схемы", "https://////wiki.telnor.ru/n/a"],
  ["порт по умолчанию", "https://wiki.telnor.ru:443/n/a"],
  ["порт по умолчанию с нулями", "https://wiki.telnor.ru:0443/n/a"],
  ["пустой порт", "https://wiki.telnor.ru:/n/a"],
  ["пустой userinfo", "https://@wiki.telnor.ru/n/a"],
  ["пустые логин и пароль", "https://:@wiki.telnor.ru/n/a"],
  ["якорь, похожий на адрес", "https://wiki.telnor.ru/n/a#//evil.example"],
  ["якорь с @", "https://wiki.telnor.ru/n/a#@evil.example"],
  ["якорь javascript:", "https://wiki.telnor.ru/#javascript:alert(1)"],
  ["запрос с чужим адресом", "https://wiki.telnor.ru/?next=https://evil.example/"],
  ["запрос с @", "https://wiki.telnor.ru?@evil.example"],
  ["якорь сразу после хоста", "https://wiki.telnor.ru#@evil.example"],
  ["%2F%2F в пути", "https://wiki.telnor.ru/%2F%2Fevil.example"],
  ["%5C в пути", "https://wiki.telnor.ru/%5Cevil.example"],
  ["%5C%5C в пути", "https://wiki.telnor.ru/%5C%5Cevil.example"],
  ["двойное кодирование слэшей", "https://wiki.telnor.ru/%252F%252Fevil.example"],
  ["%09 в пути", "https://wiki.telnor.ru/%09/evil.example"],
  ["%00 в пути", "https://wiki.telnor.ru/%00"],
  ["двойной слэш не в начале пути", "https://wiki.telnor.ru/n//evil.example"],
  ["/../ в середине", "https://wiki.telnor.ru/n/../../../search?q=x"],
  ["@ в пути", "https://wiki.telnor.ru/@evil.example"],
  ["двоеточие в пути", "https://wiki.telnor.ru/https://evil.example/"],
  ["точка с запятой и параметры", "https://wiki.telnor.ru/;@evil.example"],
  ["очень длинный путь", `https://wiki.telnor.ru/n/${LONG}`],
  ["очень длинный запрос", `https://wiki.telnor.ru/search?q=${LONG}`],
  ["кириллица в пути и запросе", "https://wiki.telnor.ru/n/заметка?q=грабли#раздел"],
];

describe("QA safeWikiReturnUrl: обходы", () => {
  it.each(MUST_REJECT)("отсекает: %s", (_name, raw) => {
    expect(safeWikiReturnUrl(raw, SITE)).toBeNull();
  });

  it.each(MAY_ACCEPT)("null или адрес на origin вики: %s", (_name, raw) => {
    const result = safeWikiReturnUrl(raw, SITE);
    if (result !== null) expectOnWiki(result);
  });

  it("принятое значение не уносит с собой чужой хост из исходной строки", () => {
    // Хост результата — от адреса сайта, а не из значения: регистр и запись хоста чужие
    expect(safeWikiReturnUrl("hTtPs://WiKi.TeLnOr.Ru/N/a?Q=1#H", SITE)).toBe(`${WIKI}/N/a?Q=1#H`);
    expect(safeWikiReturnUrl("https:wiki.telnor.ru/n/a", SITE)).toBe(`${WIKI}/n/a`);
  });

  it("перебор: случайные склейки опасных кусков не дают адреса вне вики", () => {
    const parts = [
      "https:",
      "http:",
      "HTTPS:",
      "javascript:",
      "//",
      "/",
      "\\",
      "///",
      "@",
      ":",
      "#",
      "?",
      ".",
      "wiki.telnor.ru",
      "WIKI.TELNOR.RU",
      "telnor.ru",
      "evil.example",
      "wiki.",
      "%2e",
      "%2f",
      "%5c",
      "%40",
      "%09",
      "%00",
      "..",
      "[::1]",
      "127.0.0.1",
      ":443",
      ":8443",
      "xn--",
      "\t",
      " ",
      "n/a",
    ];
    // Простой детерминированный генератор — тест воспроизводим
    let seed = 20261005;
    const rnd = (n: number) => {
      seed = (seed * 1103515245 + 12345) & 0x7fffffff;
      return seed % n;
    };
    let accepted = 0;
    for (let i = 0; i < 20_000; i++) {
      const tail = Array.from({ length: 1 + rnd(7) }, () => parts[rnd(parts.length)]).join("");
      // Часть значений начинается с «честного» начала — так больше принятых и проверенных
      const raw = ["", "https://wiki.telnor.ru", "https://wiki.telnor.ru/"][rnd(3)] + tail;
      const result = safeWikiReturnUrl(raw, SITE);
      if (result === null) continue;
      accepted++;
      expectOnWiki(result);
    }
    // Перебор не вырожден: часть значений действительно принимается
    expect(accepted).toBeGreaterThan(1000);
  });
});

describe("QA возврат: адрес, собранный вики, сайт принимает и возвращает ровно туда же", () => {
  /** Что вики кладёт в next и что сайт из него достаёт (как useSearchParams в LoginPage). */
  function roundTrip(pathname: string, search = "", hash = ""): string | null {
    const login = siteLoginUrl(wikiReturnPath({ pathname, search, hash }), WIKI_LOC) as string;
    const url = new URL(login);
    expect(url.origin + url.pathname).toBe("https://telnor.ru/login");
    return safeWikiReturnUrl(url.searchParams.get("next"), SITE);
  }

  it.each([
    ["/", "", ""],
    ["/n/moi-domashnii-sait/grabli", "", ""],
    ["/n/a/b", "?x=1", "#section"],
    ["/search", "?q=a%26b&tag=k8s&project=home-page", "#top"],
    ["/search", "?q=%D0%B3%D1%80%D0%B0%D0%B1%D0%BB%D0%B8", ""],
    ["/search", "?q=a+b%20c", ""],
    ["/search", "?q=C%3A%5CUsers", ""],
    ["/n/a%20b/c%2Fd", "", "#%D1%80%D0%B0%D0%B7%D0%B4%D0%B5%D0%BB"],
    ["/b/11111111-2222-3333-4444-555555555555", "", ""],
    ["/n/a", "?next=https%3A%2F%2Fevil.example", "#//evil.example"],
    ["/no-such-page", "?a=1&a=2", ""],
  ])("%s%s%s", (pathname, search, hash) => {
    expect(roundTrip(pathname, search, hash)).toBe(`${WIKI}${pathname}${search}${hash}`);
  });

  it("страница вики с путём // на сайте отсекается — вход закончится главной сайта, не чужим адресом", () => {
    expect(roundTrip("//evil.example/n/a")).toBeNull();
  });

  // Принятое поведение, не дефект (решение Никиты от 2026-10-05, задача трекера 12, D4):
  // браузер не кодирует обратный слэш в запросе и якоре, вики кладёт его в next как есть,
  // а сайт любые значения с обратным слэшем отбрасывает — безопасный отказ. После входа
  // человек оказывается на главной сайта, а не на своей странице вики; чужого адреса нет.
  // Сама вики такие ссылки не строит (кодирует как %5C) — это только адрес, набранный руками.
  it.each([
    ["в запросе", "/search", "?q=C:\\Users", ""],
    ["в якоре", "/n/a/b", "", "#a\\b"],
    ["в запросе и якоре", "/search", "?q=\\\\evil.example", "#\\"],
  ])(
    "обратный слэш %s: адрес возврата отбрасывается целиком (null)",
    (_name, pathname, search, hash) => {
      expect(roundTrip(pathname, search, hash)).toBeNull();
    }
  );

  it("тот же адрес с закодированным обратным слэшем (%5C) возвращается как есть", () => {
    expect(roundTrip("/search", "?q=C%3A%5CUsers")).toBe(`${WIKI}/search?q=C%3A%5CUsers`);
  });
});

describe("QA возврат: несколько параметров next", () => {
  /** Как LoginPage: первый next из строки запроса. */
  const fromQuery = (query: string) =>
    safeWikiReturnUrl(new URLSearchParams(query).get("next"), SITE);

  it("берётся первый next; чужой адрес вторым параметром не подхватывается", () => {
    expect(
      fromQuery("next=https%3A%2F%2Fwiki.telnor.ru%2Fn%2Fa&next=https%3A%2F%2Fevil.example")
    ).toBe(`${WIKI}/n/a`);
    expect(
      fromQuery("next=https%3A%2F%2Fevil.example&next=https%3A%2F%2Fwiki.telnor.ru%2Fn%2Fa")
    ).toBeNull();
  });

  it("дважды закодированный адрес вики не раскодируется второй раз", () => {
    expect(fromQuery("next=https%253A%252F%252Fwiki.telnor.ru%252F")).toBeNull();
  });

  it("плюс в next — это пробел: значение отсекается", () => {
    expect(fromQuery("next=https://wiki.telnor.ru/n/a+b")).toBeNull();
  });
});
