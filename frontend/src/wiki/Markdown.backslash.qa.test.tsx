// QA: обратный слэш в адресе ссылки (GHSA-wrjc-x8rr-h8h6, задача трекера 20).
// Браузер читает «/\host» как «//host», то есть как адрес чужого сайта. Текст заметки
// считаем недоверенным: ссылка из него либо остаётся внутри вики, либо честно оформлена
// как внешняя (новая вкладка, без opener). Настоящие Markdown и BrowserRouter, без подмен.
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { Markdown } from "./Markdown";

const ORIGIN = "http://localhost:3000";
const START = "/n/a/b";

// Vitest кладёт экземпляр JSDOM в глобальную переменную jsdom. Сам переход на другой
// документ jsdom не выполняет, а сообщает о нём ошибкой «Not implemented: navigation…».
interface VirtualConsole {
  on(event: "jsdomError", listener: (error: Error) => void): void;
  off(event: "jsdomError", listener: (error: Error) => void): void;
}
const dom = (globalThis as unknown as { jsdom: { virtualConsole: VirtualConsole } }).jsdom;

let navigations: string[] = [];
const onJsdomError = (error: Error) => {
  if (/not implemented: navigation/i.test(error.message)) navigations.push(error.message);
};

let drains = 0;

/**
 * Дожидается всех переходов, которые jsdom поставил в очередь к этому моменту.
 * Переход по клику на ссылку jsdom выполняет не сразу, а отложенно, по очереди. Ставим
 * в ту же очередь свой безобидный переход на якорь и ждём, пока адрес его получит:
 * всё, что встало в очередь раньше, к этому времени уже выполнено. Случайной паузы нет.
 * Якорь остаётся в адресе, поэтому точный адрес проверяй до вызова.
 */
async function drainNavigationQueue(): Promise<void> {
  const marker = document.createElement("a");
  marker.setAttribute("href", `#qa-drain-${++drains}`);
  document.body.appendChild(marker);
  try {
    fireEvent.click(marker);
    await waitFor(() => expect(window.location.hash).toBe(marker.getAttribute("href")));
  } finally {
    marker.remove();
  }
}

/** Адрес глазами роутера */
function Where() {
  const location = useLocation();
  return <output data-testid="where">{location.pathname + location.search + location.hash}</output>;
}

const routerAddress = () => screen.getByTestId("where").textContent;
const browserAddress = () =>
  window.location.pathname + window.location.search + window.location.hash;

function renderNote(content: string) {
  return render(
    <BrowserRouter>
      <Routes>
        <Route
          path="*"
          element={
            <>
              <Markdown content={content} />
              <Where />
            </>
          }
        />
      </Routes>
    </BrowserRouter>
  ).container;
}

beforeEach(() => {
  navigations = [];
  dom.virtualConsole.on("jsdomError", onJsdomError);
  window.history.replaceState(null, "", START);
});

afterEach(() => {
  dom.virtualConsole.off("jsdomError", onJsdomError);
  window.history.replaceState(null, "", "/");
});

describe("QA обратный слэш: контроль самой проверки", () => {
  it("обычная ссылка с href «/\\host» ведёт наружу, и проверка это видит", async () => {
    const host = document.createElement("div");
    host.innerHTML = '<a href="/\\evil.example">x</a>';
    document.body.appendChild(host);
    try {
      const a = host.querySelector("a")!;
      expect(new URL(a.getAttribute("href")!, window.location.href).origin).toBe(
        "http://evil.example"
      );

      fireEvent.click(a);

      // Переход только поставлен в очередь. Отрицательные проверки ниже полагаются на
      // drainNavigationQueue, поэтому здесь ждём именно им: он обязан дождаться перехода,
      // а его собственный якорь за уход со страницы не считается
      expect(navigations).toEqual([]);
      await drainNavigationQueue();
      expect(navigations).toHaveLength(1);
    } finally {
      host.remove();
    }
  });
});

describe("QA обратный слэш: ссылка из текста заметки не уводит с вики", () => {
  // Обратный слэш в адресе кодируется как %5C — это обычный путь на своём сайте
  it.each([
    ["обратный слэш", "[x](/\\evil.example)", "/%5Cevil.example"],
    ["уже закодированный", "[x](/%5Cevil.example)", "/%5Cevil.example"],
    ["экранированный обратный слэш", "[x](/\\\\evil.example)", "/%5Cevil.example"],
    ["в угловых скобках", "[x](</\\evil.example>)", "/%5Cevil.example"],
    ["числовая сущность", "[x](/&#92;evil.example)", "/%5Cevil.example"],
    ["именованная сущность", "[x](/&bsol;evil.example)", "/%5Cevil.example"],
    ["ссылка-сноска", "[x][r]\n\n[r]: /\\evil.example", "/%5Cevil.example"],
    [
      "обратный слэш в запросе и якоре",
      "[x](/n/a?q=\\\\evil.example#\\evil.example)",
      "/n/a?q=%5Cevil.example#%5Cevil.example",
    ],
    ["обратный слэш после пути", "[x](/n/..\\\\..\\\\evil.example)", "/n/..%5C..%5Cevil.example"],
  ])("%s: внутренняя ссылка, переход остаётся на своём адресе", async (_name, source, expected) => {
    const container = renderNote(source);

    const links = container.querySelectorAll("a");
    expect(links).toHaveLength(1);
    const raw = links[0].getAttribute("href") ?? "";
    expect(raw).toBe(expected);
    expect(new URL(raw, window.location.href).origin).toBe(ORIGIN);
    expect(links[0]).not.toHaveAttribute("target");

    fireEvent.click(links[0]);

    // Переход состоялся, и он внутри вики: адрес сменился на свой путь
    expect(browserAddress()).toBe(expected);
    expect(routerAddress()).toBe(expected);
    await drainNavigationQueue();
    expect(navigations).toEqual([]);
    expect(window.location.origin).toBe(ORIGIN);
  });

  // «\/» в Markdown — экранированный «/», то есть адрес «//host»: это внешняя ссылка
  it.each([
    ["два слэша", "[x](//evil.example)"],
    ["слэш, обратный слэш, слэш", "[x](/\\/evil.example)"],
  ])(
    "%s: внешняя ссылка — новая вкладка без opener, роутер её не трогает",
    async (_name, source) => {
      const container = renderNote(source);

      const links = container.querySelectorAll("a");
      expect(links).toHaveLength(1);
      expect(links[0]).toHaveAttribute("href", "//evil.example");
      expect(links[0]).toHaveAttribute("target", "_blank");
      expect(links[0].getAttribute("rel")).toContain("noopener");
      expect(links[0].getAttribute("rel")).toContain("noreferrer");

      fireEvent.click(links[0]);

      // Клик достался браузеру (новая вкладка): текущая вкладка осталась на своём адресе —
      // роутер не перехватил клик и не увёл её ни на свой путь, ни на чужой сайт
      expect(browserAddress()).toBe(START);
      expect(routerAddress()).toBe(START);
      await drainNavigationQueue();
      expect(navigations).toEqual([]);
    }
  );

  // Адрес без «/» в начале Markdown.tsx оформляет как внешний. Здесь он относительный:
  // обратные слэши закодированы, и ведёт он на свой сайт, а не на «\\host» = «//host»
  it("два обратных слэша: ссылка в новой вкладке, адрес — на своём сайте", () => {
    const container = renderNote("[x](\\\\\\\\evil.example)");

    const links = container.querySelectorAll("a");
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute("href", "%5C%5Cevil.example");
    expect(new URL("%5C%5Cevil.example", window.location.href).href).toBe(
      `${ORIGIN}/n/a/%5C%5Cevil.example`
    );
    expect(links[0]).toHaveAttribute("target", "_blank");
    expect(links[0].getAttribute("rel")).toContain("noopener");
    expect(links[0].getAttribute("rel")).toContain("noreferrer");
  });

  // Разбор Markdown ссылку здесь не находит вовсе: нажимать нечего, текст выведен как есть
  it.each([
    ["табуляция и обратный слэш", "[x](/\t\\evil.example)", "[x](/ \\evil.example)"],
    ["автоссылка", "</\\evil.example>", "</\\evil.example>"],
  ])("%s: ссылки нет, написанное выведено текстом", (_name, source, text) => {
    const container = renderNote(source);

    expect(container.querySelectorAll("a")).toHaveLength(0);
    expect(container.querySelectorAll("[href], [src]")).toHaveLength(0);
    expect(container.querySelector(".wiki-md")).toHaveTextContent(text, {
      normalizeWhitespace: true,
    });
  });
});

describe("QA обратный слэш: роутер отказывает в переходе на чужой адрес", () => {
  // Проверка самого обновления: в 7.14.0 такой переход доходил до window.location.assign.
  // Как именно роутер отказывает — ошибкой или молча — тесту не важно, важен итог:
  // вкладку не попросили уйти на другой документ.
  function Go({ to }: Readonly<{ to: string }>) {
    const navigate = useNavigate();
    return (
      <button
        onClick={() => {
          try {
            Promise.resolve(navigate(to)).catch(() => undefined);
          } catch {
            // отказ ошибкой — один из допустимых исходов
          }
        }}
      >
        перейти
      </button>
    );
  }

  function renderGo(to: string) {
    render(
      <BrowserRouter>
        <Go to={to} />
        <Where />
      </BrowserRouter>
    );
  }

  it.each([
    "/\\evil.example",
    "/\\/evil.example",
    "\\\\evil.example",
    "/\\\\evil.example",
    "//evil.example",
  ])("navigate(%j) — ухода на другой документ нет, вкладка на своём сайте", async (to) => {
    renderGo(to);

    fireEvent.click(screen.getByRole("button", { name: "перейти" }));

    // location.assign jsdom отмечает сразу, переход по ссылке — через очередь
    expect(navigations).toEqual([]);
    await drainNavigationQueue();
    expect(navigations).toEqual([]);
    expect(window.location.origin).toBe(ORIGIN);
  });

  it("закодированный обратный слэш — обычный путь на своём сайте", async () => {
    renderGo("/%5Cevil.example");

    fireEvent.click(screen.getByRole("button", { name: "перейти" }));

    expect(window.location.href).toBe(`${ORIGIN}/%5Cevil.example`);
    expect(routerAddress()).toBe("/%5Cevil.example");
    await drainNavigationQueue();
    expect(navigations).toEqual([]);
  });
});
