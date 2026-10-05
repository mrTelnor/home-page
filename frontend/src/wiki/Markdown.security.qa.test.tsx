// QA: безопасность рендера Markdown. Заметки пишут агенты, поэтому текст заметки
// считаем недоверенным: ни сырой HTML, ни опасные схемы ссылок не должны дойти до DOM.
import { afterEach, describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { type WikiNoteLink } from "@/api/types";
import { Markdown } from "./Markdown";

const FORBIDDEN_TAGS =
  "script, iframe, svg, math, object, embed, style, form, link, meta, base, frame, frameset, applet, video, audio, details, button, textarea, select";
const SAFE_LINK_PROTOCOLS = ["http:", "https:", "mailto:"];
const SAFE_IMAGE_PROTOCOLS = ["http:", "https:"];
// Перед схемой допускаем любые не-буквы: пробелы и управляющие символы браузер отбрасывает
const DANGEROUS_SCHEME = /^[^\p{L}/?#]*(javascript|data|vbscript|file|blob)\s*:/iu;

function renderMd(content: string, links: WikiNoteLink[] = []) {
  return render(
    <MemoryRouter>
      <Markdown content={content} links={links} />
    </MemoryRouter>
  ).container;
}

/** Общая проверка: в DOM нет исполняемого содержимого. */
function expectSafe(container: HTMLElement) {
  expect(container.querySelectorAll(FORBIDDEN_TAGS)).toHaveLength(0);
  for (const el of container.querySelectorAll("*")) {
    for (const attr of el.getAttributeNames()) {
      expect(attr.toLowerCase().startsWith("on"), `обработчик ${attr} на <${el.tagName}>`).toBe(
        false
      );
      expect(["style", "srcdoc", "formaction"]).not.toContain(attr.toLowerCase());
    }
  }
  for (const a of container.querySelectorAll("a")) {
    const raw = a.getAttribute("href") ?? "";
    expect(raw, "href ссылки").not.toMatch(DANGEROUS_SCHEME);
    expect(SAFE_LINK_PROTOCOLS).toContain(new URL(raw, window.location.href).protocol);
  }
  for (const img of container.querySelectorAll("img")) {
    const raw = img.getAttribute("src") ?? "";
    expect(raw, "src картинки").not.toMatch(DANGEROUS_SCHEME);
    expect(SAFE_IMAGE_PROTOCOLS).toContain(new URL(raw, window.location.href).protocol);
  }
  expect((window as unknown as Record<string, unknown>).__qaXss).toBeUndefined();
}

afterEach(() => {
  delete (window as unknown as Record<string, unknown>).__qaXss;
});

describe("QA Markdown: контроль самой проверки", () => {
  // Если бы сырой HTML попал в DOM, expectSafe это заметила бы
  it.each([
    "<script>1</script>",
    '<img src="x" onerror="1">',
    '<a href="javascript:alert(1)">x</a>',
    '<a href=" JaVaScRiPt:alert(1)">x</a>',
    '<img src="data:image/svg+xml;base64,AAAA">',
    '<svg onload="1"></svg>',
    '<p style="color:red">x</p>',
  ])("expectSafe ловит %s", (html) => {
    const host = document.createElement("div");
    host.innerHTML = html;
    expect(() => expectSafe(host)).toThrow();
  });
});

describe("QA Markdown: сырой HTML остаётся текстом", () => {
  it.each([
    ["script блоком", "<script>window.__qaXss = 1</script>"],
    ["script в строке", "текст <script>window.__qaXss = 1</script> текст"],
    ["script с переносами", "<script\n>window.__qaXss = 1</script\n>"],
    ["SCRIPT в верхнем регистре", "<SCRIPT SRC=//evil.example/x.js></SCRIPT>"],
    ["img onerror", '<img src="x" onerror="window.__qaXss = 1">'],
    ["img onerror в строке", "текст <img src=x onerror=window.__qaXss=1> текст"],
    ["iframe", '<iframe src="javascript:window.__qaXss = 1"></iframe>'],
    ["iframe srcdoc", '<iframe srcdoc="<script>window.__qaXss = 1</script>"></iframe>'],
    ["svg onload", '<svg onload="window.__qaXss = 1"><circle r="1"/></svg>'],
    ["svg в строке", "текст <svg/onload=window.__qaXss=1> текст"],
    ["a href=javascript: как HTML", '<a href="javascript:window.__qaXss = 1">жми</a>'],
    ["a onclick", '<a href="#" onclick="window.__qaXss = 1">жми</a>'],
    ["math", "<math><mtext><script>window.__qaXss = 1</script></mtext></math>"],
    ["object", '<object data="javascript:window.__qaXss = 1"></object>'],
    ["embed", '<embed src="javascript:window.__qaXss = 1">'],
    ["style", "<style>body { display: none }</style>"],
    ["form", '<form action="javascript:window.__qaXss = 1"><button>ok</button></form>'],
    ["details ontoggle", '<details open ontoggle="window.__qaXss = 1">x</details>'],
    ["base", '<base href="https://evil.example/">'],
    ["meta refresh", '<meta http-equiv="refresh" content="0;url=https://evil.example">'],
    ["link stylesheet", '<link rel="stylesheet" href="https://evil.example/x.css">'],
    ["video onerror", '<video src=x onerror="window.__qaXss = 1"></video>'],
    ["HTML в цитате", "> <script>window.__qaXss = 1</script>"],
    [
      "HTML в списке",
      "- <img src=x onerror=window.__qaXss=1>\n- <iframe src=//evil.example></iframe>",
    ],
    ["HTML в заголовке", "# Заголовок <img src=x onerror=window.__qaXss=1>"],
    ["HTML в выделении", "**<script>window.__qaXss = 1</script>**"],
    ["HTML в тексте ссылки", "[<img src=x onerror=window.__qaXss=1>](https://example.org)"],
    [
      "комментарий и CDATA",
      "<!-- <script>window.__qaXss = 1</script> -->\n\n<![CDATA[<script>window.__qaXss = 1</script>]]>",
    ],
    [
      "сущности вместо скобок",
      "&lt;script&gt;window.__qaXss = 1&lt;/script&gt; &#60;img src=x onerror=1&#62;",
    ],
  ])("%s", (_name, source) => {
    const container = renderMd(source);
    expectSafe(container);
    expect(container.querySelector("img")).toBeNull();
  });

  it("div со style и классом не становится элементом", () => {
    const container = renderMd(
      '<div style="position:fixed;inset:0" class="fixed">перекрытие</div>'
    );
    expectSafe(container);
    expect(container.querySelector(".fixed")).toBeNull();
  });
});

describe("QA Markdown: ссылки с опасными схемами", () => {
  it.each([
    ["javascript:", "[x](javascript:alert(1))"],
    ["регистр", "[x](JaVaScRiPt:alert(1))"],
    ["пробел перед схемой", "[x]( javascript:alert(1))"],
    ["в угловых скобках", "[x](<javascript:alert(1)>)"],
    ["пробел внутри угловых скобок", "[x](< javascript:alert(1)>)"],
    ["табуляция в схеме", "[x](<java\tscript:alert(1)>)"],
    ["сущность в схеме", "[x](&#106;avascript:alert(1))"],
    ["hex-сущность в схеме", "[x](&#x6A;avascript:alert(1))"],
    ["сущность-двоеточие", "[x](javascript&colon;alert(1))"],
    ["числовое двоеточие", "[x](javascript&#58;alert(1))"],
    ["управляющий символ перед схемой", "[x](\u0001javascript:alert(1))"],
    ["javascript:// с переводом строки", "[x](javascript://%0Aalert(1))"],
    ["data:", "[x](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)"],
    ["DATA: регистр", "[x](DATA:text/html,alert)"],
    ["vbscript:", "[x](vbscript:msgbox(1))"],
    ["VbScript: регистр", "[x](VbScRiPt:msgbox(1))"],
    ["file:", "[x](file:///etc/passwd)"],
    ["blob:", "[x](blob:https://evil.example/1)"],
    ["ссылка-сноска", "[x][r]\n\n[r]: javascript:alert(1)"],
    ["ссылка-сноска data:", "[x][r]\n\n[r]: <data:text/html,alert>"],
    ["автоссылка", "<javascript:alert(1)>"],
    ["автоссылка data:", "<data:text/html,alert>"],
    ["автоссылка vbscript:", "<vbscript:msgbox(1)>"],
    ["в ячейке таблицы", "| a |\n|---|\n| [x](javascript:alert(1)) |"],
    ["в заголовке ссылки", '[x](javascript:alert(1) "title")'],
  ])("%s", (_name, source) => {
    const container = renderMd(source);
    expectSafe(container);
    for (const a of container.querySelectorAll("a")) {
      const href = a.getAttribute("href") ?? "";
      expect(href).not.toMatch(/script|data:|file:|blob:/i);
    }
  });

  it("обычные ссылки при этом работают", () => {
    const container = renderMd(
      "[a](https://example.org/x?y=1#z) [b](http://example.org) [c](mailto:a@example.org) [d](/n/a/b) [e](#раздел)"
    );
    const hrefs = [...container.querySelectorAll("a")].map((a) => a.getAttribute("href"));
    expect(hrefs).toEqual([
      "https://example.org/x?y=1#z",
      "http://example.org",
      "mailto:a@example.org",
      "/n/a/b",
      "#%D1%80%D0%B0%D0%B7%D0%B4%D0%B5%D0%BB",
    ]);
    expectSafe(container);
  });

  it("внешняя ссылка, в том числе вида //host, открывается в новой вкладке без opener", () => {
    const container = renderMd("[a](https://example.org) [b](//evil.example/x)");
    for (const a of container.querySelectorAll("a")) {
      expect(a).toHaveAttribute("target", "_blank");
      expect(a.getAttribute("rel")).toContain("noopener");
      expect(a.getAttribute("rel")).toContain("noreferrer");
    }
    expect(container.querySelectorAll("a")).toHaveLength(2);
  });
});

describe("QA Markdown: картинки", () => {
  it.each([
    ["javascript:", "![x](javascript:alert(1))"],
    ["регистр и пробел", "![x]( JaVaScRiPt:alert(1))"],
    ["data: svg", "![x](data:image/svg+xml;base64,PHN2ZyBvbmxvYWQ9YWxlcnQoMSk+)"],
    ["data: html", "![x](data:text/html,alert)"],
    ["vbscript:", "![x](vbscript:msgbox(1))"],
    ["сноска", "![x][r]\n\n[r]: javascript:alert(1)"],
    ["в таблице", "| a |\n|---|\n| ![x](javascript:alert(1)) |"],
    ["картинка-ссылка", "[![x](javascript:alert(1))](javascript:alert(2))"],
  ])("%s — src с опасной схемой не выставляется", (_name, source) => {
    const container = renderMd(source);
    expectSafe(container);
    for (const img of container.querySelectorAll("img")) {
      expect(img.getAttribute("src") ?? "").toBe("");
    }
  });

  it("alt и title с кавычками и скобками не создают атрибутов и элементов", () => {
    const container = renderMd(
      '![a" onerror="window.__qaXss=1](https://example.org/a.png "t\\" onload=\\"window.__qaXss=1")'
    );
    expectSafe(container);
    const img = container.querySelector("img");
    expect(img).not.toBeNull();
    expect(img?.getAttributeNames().sort()).toEqual([
      "alt",
      "loading",
      "referrerpolicy",
      "src",
      "title",
    ]);
  });

  // Фиксирует текущее поведение (замечание QA, решение за Никитой): картинка с чужого
  // адреса загружается браузером админа — чужой сервер узнаёт о просмотре заметки.
  it("картинка с внешнего адреса разрешена: без Referer и с ленивой загрузкой", () => {
    const container = renderMd("![пиксель](https://tracker.example/pixel.png?note=1)");
    const img = container.querySelector("img");
    expect(img).toHaveAttribute("src", "https://tracker.example/pixel.png?note=1");
    expect(img).toHaveAttribute("referrerpolicy", "no-referrer");
    expect(img).toHaveAttribute("loading", "lazy");
  });
});

describe("QA Markdown: таблицы GFM с HTML в ячейках", () => {
  it("теги в ячейках и заголовках остаются текстом, таблица рендерится", () => {
    const container = renderMd(
      [
        "| <script>window.__qaXss = 1</script> | b |",
        "|---|---|",
        "| <img src=x onerror=window.__qaXss=1> | <iframe src=//evil.example></iframe> |",
        '| <svg onload=window.__qaXss=1> | <a href="javascript:window.__qaXss=1">x</a> |',
      ].join("\n")
    );
    expectSafe(container);
    expect(container.querySelectorAll("table")).toHaveLength(1);
    expect(container.querySelectorAll("tbody tr")).toHaveLength(2);
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<script>");
  });
});

describe("QA Markdown: содержимое [[…]]", () => {
  const links: WikiNoteLink[] = [
    { slug: "site/arch", title: "Архитектура", alias: null },
    {
      slug: "site/quotes",
      title: "Заметка \"в кавычках\" и 'апострофах' a < b > c & d",
      alias: null,
    },
  ];

  it.each([
    ["тег в названии", "[[<img src=x onerror=window.__qaXss=1>]]"],
    ["script в названии", "[[<script>window.__qaXss = 1</script>]]"],
    ["тег в алиасе", "[[Архитектура|<img src=x onerror=window.__qaXss=1>]]"],
    ["script в алиасе", "[[Архитектура|<script>window.__qaXss = 1</script>]]"],
    ["svg в алиасе", "[[Архитектура|<svg onload=window.__qaXss=1>]]"],
    ["название в теге", "[[<b onmouseover=window.__qaXss=1>Архитектура</b>]]"],
    ["ссылка javascript: внутри", "[[Архитектура|[x](javascript:alert(1))]]"],
    ["javascript: как название", "[[javascript:alert(1)]]"],
    ["javascript: как алиас", "[[Архитектура|javascript:alert(1)]]"],
    [
      "в ячейке таблицы",
      "| a |\n|---|\n| [[Архитектура\\|<img src=x onerror=window.__qaXss=1>]] |",
    ],
  ])("%s", (_name, source) => {
    const container = renderMd(source, links);
    expectSafe(container);
    expect(container.querySelector("img, b")).toBeNull();
  });

  it("кавычки, апострофы и угловые скобки в названии — обычный текст ссылки", () => {
    const container = renderMd(`См. [[Заметка "в кавычках" и 'апострофах' a < b > c & d]].`, links);
    expectSafe(container);
    const a = container.querySelector("a");
    expect(a).toHaveAttribute("href", "/n/site/quotes");
    expect(a?.textContent).toBe(`Заметка "в кавычках" и 'апострофах' a < b > c & d`);
    // Кавычки из названия не породили новых атрибутов
    const extra = (a?.getAttributeNames() ?? []).filter(
      (n) => !["class", "href", "data-discover"].includes(n)
    );
    expect(extra).toEqual([]);
  });

  it("кавычки и скобки в алиасе — обычный текст, атрибутов не добавляют", () => {
    const container = renderMd(`[[Архитектура|" onclick="window.__qaXss=1" x=' a < b > c]]`, links);
    expectSafe(container);
    const a = container.querySelector("a");
    expect(a).toHaveAttribute("href", "/n/site/arch");
    expect(a?.textContent).toBe(`" onclick="window.__qaXss=1" x=' a < b > c`);
  });

  it("неразрешённая ссылка с кавычками и скобками — серый текст без лишних атрибутов", () => {
    const container = renderMd(`[[Нет " такой ' < заметки >|" title="x]]`, links);
    expectSafe(container);
    expect(container.querySelector("a")).toBeNull();
    const span = container.querySelector(".wiki-link-unresolved");
    expect(span?.textContent).toBe(`" title="x`);
    expect(span?.getAttribute("title")).toBe("Заметка не найдена");
    expect(span?.getAttributeNames().sort()).toEqual(["class", "title"]);
  });
});

describe("QA Markdown: slug из links не делает ссылку внешней или исполняемой", () => {
  it.each([
    "javascript:alert(1)",
    "JaVaScRiPt:alert(1)",
    " javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "//evil.example",
    "//evil.example/x",
    "/\\evil.example",
    "\\\\evil.example",
    "https://evil.example",
    "https:evil.example",
    "/https://evil.example",
    "../../login",
    "..//evil.example",
    "a/../../..//evil.example",
    "\t//evil.example",
    "#x",
    "?next=//evil.example",
    "",
  ])("slug %j", (slug) => {
    const container = renderMd("Цель: [[Цель]].", [{ slug, title: "Цель", alias: null }]);
    expectSafe(container);
    const a = container.querySelector("a");
    expect(a).not.toBeNull();
    const raw = a?.getAttribute("href") ?? "";
    // Внутренняя ссылка: путь от корня вики, тот же origin, без новой вкладки
    expect(raw.startsWith("/")).toBe(true);
    expect(raw.startsWith("//")).toBe(false);
    expect(raw.startsWith("/\\")).toBe(false);
    expect(new URL(raw, "https://wiki.example.test/n/a").origin).toBe("https://wiki.example.test");
    expect(a).not.toHaveAttribute("target");
    expect(a).toHaveClass("wiki-link");
  });
});

describe("QA вики: в рабочем коде нет небезопасной вставки HTML", () => {
  const sources = import.meta.glob<string>(["./**/*.{ts,tsx}", "!./**/*.test.{ts,tsx}"], {
    query: "?raw",
    import: "default",
    eager: true,
  });

  it("исходники вики найдены", () => {
    expect(Object.keys(sources)).toEqual(
      expect.arrayContaining(["./Markdown.tsx", "./wikiLinks.ts"])
    );
  });

  it.each([
    "dangerouslySetInnerHTML",
    "innerHTML",
    "outerHTML",
    "insertAdjacentHTML",
    "document.write",
    "eval(",
  ])("нет %s", (needle) => {
    const hits = Object.entries(sources)
      .filter(([, text]) => text.includes(needle))
      .map(([file]) => file);
    expect(hits).toEqual([]);
  });

  it("rehype-raw и другие плагины сырого HTML не подключены", () => {
    for (const [file, text] of Object.entries(sources)) {
      const imports = text.split("\n").filter((line) => /^\s*import\b/.test(line));
      expect(
        imports.filter((line) => /rehype-raw|rehypeRaw|allowDangerousHtml|skipHtml/.test(line)),
        file
      ).toEqual([]);
      expect(text.includes("allowDangerousHtml"), file).toBe(false);
      expect(text.includes("urlTransform"), `${file}: urlTransform переопределён`).toBe(false);
    }
  });
});
