import { describe, expect, it } from "vitest";
import { type WikiNoteLink } from "@/api/types";
import { resolveWikiLink } from "./wikiLinks";

const links: WikiNoteLink[] = [
  { slug: "site/readme", title: "README", alias: null },
  { slug: "work/readme", title: "README", alias: "индекс работы" },
  { slug: "site/grabli", title: "Грабли home-page", alias: null },
];

describe("resolveWikiLink", () => {
  it("находит цель по названию без учёта регистра и лишних пробелов", () => {
    expect(resolveWikiLink("  грабли   HOME-page ", null, links)?.slug).toBe("site/grabli");
  });

  it("при одинаковых названиях выбирает ссылку с совпавшим алиасом", () => {
    expect(resolveWikiLink("README", "Индекс работы", links)?.slug).toBe("work/readme");
  });

  it("без подходящего алиаса берёт первую ссылку с таким названием", () => {
    expect(resolveWikiLink("README", null, links)?.slug).toBe("site/readme");
    expect(resolveWikiLink("README", "что-то ещё", links)?.slug).toBe("site/readme");
  });

  it("нет такой исходящей ссылки — не разрешена", () => {
    expect(resolveWikiLink("Архитектура", null, links)).toBeNull();
    expect(resolveWikiLink("README", null, [])).toBeNull();
  });
});
