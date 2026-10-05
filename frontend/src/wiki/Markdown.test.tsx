import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { type WikiNoteLink } from "@/api/types";
import { Markdown } from "./Markdown";

function renderMd(content: string, links: WikiNoteLink[] = []) {
  return render(
    <MemoryRouter>
      <Markdown content={content} links={links} />
    </MemoryRouter>
  );
}

const links: WikiNoteLink[] = [
  { slug: "moi-domashnii-sait/arkhitektura", title: "Архитектура", alias: null },
  { slug: "moi-domashnii-sait/grabli", title: "Грабли home-page", alias: "грабли" },
];

describe("Markdown: сырой HTML", () => {
  it("<script> не становится элементом DOM", () => {
    const { container } = renderMd(
      "До\n\n<script>window.__wikiXss = 1</script>\n\nПосле <script>alert(1)</script>"
    );
    expect(container.querySelector("script")).toBeNull();
    expect((window as unknown as Record<string, unknown>).__wikiXss).toBeUndefined();
    // Тег виден как обычный текст
    expect(container.textContent).toContain("<script>");
  });

  it("<img onerror> не становится элементом DOM", () => {
    const { container } = renderMd(
      '<img src="x" onerror="window.__wikiXss = 2">\n\nтекст <img src=x onerror=alert(1)> дальше'
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("[onerror]")).toBeNull();
    expect(container.textContent).toContain("onerror");
  });

  it("прочие теги и обработчики тоже остаются текстом", () => {
    const { container } = renderMd(
      '<iframe src="https://example.org"></iframe>\n\n<a href="#" onclick="alert(1)">клик</a>\n\n<div style="color:red">блок</div>'
    );
    expect(container.querySelector("iframe")).toBeNull();
    expect(container.querySelector("[onclick]")).toBeNull();
    expect(container.querySelector("[style]")).toBeNull();
  });

  it("ссылка со схемой javascript: не получает опасный href", () => {
    const { container } = renderMd("[жми](javascript:alert(1))");
    for (const a of container.querySelectorAll("a")) {
      expect(a.getAttribute("href") ?? "").not.toMatch(/^\s*javascript:/i);
    }
  });
});

describe("Markdown: ссылки [[…]]", () => {
  it("[[Название]] ведёт на заметку из исходящих ссылок", () => {
    renderMd("См. [[Архитектура]] проекта.", links);
    const link = screen.getByRole("link", { name: "Архитектура" });
    expect(link).toHaveAttribute("href", "/n/moi-domashnii-sait/arkhitektura");
    expect(link).toHaveClass("wiki-link");
    // Внутренняя ссылка открывается в этой же вкладке
    expect(link).not.toHaveAttribute("target");
  });

  it("[[Название|алиас]] показывает алиас", () => {
    renderMd("Перед работой — [[Грабли home-page|грабли]].", links);
    const link = screen.getByRole("link", { name: "грабли" });
    expect(link).toHaveAttribute("href", "/n/moi-domashnii-sait/grabli");
    expect(screen.queryByText(/Грабли home-page/)).not.toBeInTheDocument();
  });

  it("неразрешённая ссылка — серый текст, а не ссылка", () => {
    const { container } = renderMd("Есть [[Нет такой заметки]] и [[Тоже нет|подпись]].", links);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    const unresolved = container.querySelectorAll(".wiki-link-unresolved");
    expect(unresolved).toHaveLength(2);
    expect(unresolved[0]).toHaveTextContent("Нет такой заметки");
    expect(unresolved[1]).toHaveTextContent("подпись");
    expect(container.textContent).not.toContain("[[");
  });

  it("несколько ссылок в одной строке и текст между ними сохраняются", () => {
    const { container } = renderMd("A [[Архитектура]], B [[Грабли home-page]] C", links);
    expect(screen.getAllByRole("link")).toHaveLength(2);
    expect(container.textContent).toBe("A Архитектура, B Грабли home-page C");
  });

  it("в коде [[…]] остаётся как есть", () => {
    const { container } = renderMd("`[[Архитектура]]`\n\n```\n[[Архитектура]]\n```", links);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(container.querySelectorAll("code")).toHaveLength(2);
    expect(container.textContent).toContain("[[Архитектура]]");
  });

  it("ссылка в ячейке таблицы разрешается", () => {
    renderMd("| Что | Где |\n|---|---|\n| схема | [[Архитектура]] |", links);
    const table = screen.getByRole("table");
    expect(within(table).getByRole("link", { name: "Архитектура" })).toHaveAttribute(
      "href",
      "/n/moi-domashnii-sait/arkhitektura"
    );
  });
});

describe("Markdown: GFM и код", () => {
  it("таблица GFM рендерится таблицей", () => {
    renderMd("| № | Грабля |\n|---|---|\n| G97 | кэш сборки |\n| G102 | права на volume |");
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("columnheader").map((th) => th.textContent)).toEqual([
      "№",
      "Грабля",
    ]);
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    expect(within(table).getByRole("cell", { name: "G102" })).toBeInTheDocument();
  });

  it("зачёркивание и список задач GFM", () => {
    const { container } = renderMd("~~старое~~\n\n- [x] сделано\n- [ ] осталось");
    expect(container.querySelector("del")).toHaveTextContent("старое");
    expect(container.querySelectorAll('input[type="checkbox"]')).toHaveLength(2);
  });

  it("блок кода с языком получает подсветку", () => {
    const { container } = renderMd("```python\ndef f():\n    return 1\n```");
    const code = container.querySelector("pre code");
    expect(code).toHaveClass("hljs");
    expect(code?.querySelector(".hljs-keyword")).toHaveTextContent("def");
  });

  it("powershell подсвечивается, неизвестный язык не ломает рендер", () => {
    const { container } = renderMd(
      "```powershell\nGet-ChildItem -Recurse\n```\n\n```fstab\nUUID=1 / ext4 defaults 0 1\n```"
    );
    const blocks = container.querySelectorAll("pre code");
    expect(blocks).toHaveLength(2);
    expect(blocks[0].querySelector("[class^='hljs-']")).not.toBeNull();
    expect(blocks[1]).toHaveTextContent("UUID=1 / ext4 defaults 0 1");
  });

  it("внешняя ссылка открывается в новой вкладке без передачи opener", () => {
    renderMd("[сайт](https://example.org)");
    const link = screen.getByRole("link", { name: "сайт" });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link.getAttribute("rel")).toContain("noopener");
  });
});
