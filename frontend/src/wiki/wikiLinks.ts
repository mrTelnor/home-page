// Ссылки вида [[Название]] и [[Название|алиас]] в тексте заметок.
// Заголовки в базе знаний повторяются, поэтому цель ищем только среди исходящих
// ссылок самой заметки (note_links), а не по названию во всей базе.
import { type WikiNoteLink } from "@/api/types";
import { notePath } from "./paths";

export const WIKI_LINK_CLASS = "wiki-link";
export const WIKI_LINK_UNRESOLVED_CLASS = "wiki-link-unresolved";

const normalize = (value: string) => value.trim().replace(/\s+/g, " ").toLowerCase();

/** Цель ссылки по названию; при нескольких заметках с одним названием — та, у которой совпал алиас. */
export function resolveWikiLink(
  title: string,
  alias: string | null,
  links: WikiNoteLink[]
): WikiNoteLink | null {
  const wanted = normalize(title);
  const candidates = links.filter((link) => normalize(link.title) === wanted);
  if (candidates.length === 0) return null;
  if (alias !== null) {
    const wantedAlias = normalize(alias);
    const byAlias = candidates.find(
      (link) => link.alias !== null && normalize(link.alias) === wantedAlias
    );
    if (byAlias) return byAlias;
  }
  return candidates[0];
}

// Минимальное описание узлов mdast — чтобы не тянуть типы unified прямой зависимостью
interface MdNode {
  type: string;
  value?: string;
  url?: string;
  children?: MdNode[];
  data?: { hName?: string; hProperties?: Record<string, unknown> };
}

const WIKI_LINK_RE = /\[\[([^[\]|\n]+)(?:\|([^[\]\n]+))?\]\]/g;

function splitText(value: string, links: WikiNoteLink[]): MdNode[] | null {
  const result: MdNode[] = [];
  let last = 0;
  for (const match of value.matchAll(WIKI_LINK_RE)) {
    const title = match[1].trim();
    const alias = match[2]?.trim() || null;
    if (!title) continue;
    const start = match.index;
    if (start > last) result.push({ type: "text", value: value.slice(last, start) });
    const label = alias ?? title;
    const target = resolveWikiLink(title, alias, links);
    if (target) {
      result.push({
        type: "link",
        url: notePath(target.slug),
        children: [{ type: "text", value: label }],
        data: { hProperties: { className: [WIKI_LINK_CLASS] } },
      });
    } else {
      result.push({
        type: "text",
        value: label,
        data: {
          hName: "span",
          hProperties: { className: [WIKI_LINK_UNRESOLVED_CLASS], title: "Заметка не найдена" },
        },
      });
    }
    last = start + match[0].length;
  }
  if (result.length === 0) return null;
  if (last < value.length) result.push({ type: "text", value: value.slice(last) });
  return result;
}

function transform(node: MdNode, links: WikiNoteLink[]): void {
  // Внутри обычной ссылки вложенную ссылку не делаем. Код (code, inlineCode) детей
  // не имеет — туда обход не заходит, [[…]] в коде остаётся текстом.
  if (!node.children || node.type === "link" || node.type === "linkReference") return;
  const next: MdNode[] = [];
  for (const child of node.children) {
    if (child.type === "text" && typeof child.value === "string" && !child.data) {
      const parts = splitText(child.value, links);
      if (parts) {
        next.push(...parts);
        continue;
      }
    } else {
      transform(child, links);
    }
    next.push(child);
  }
  node.children = next;
}

/** Плагин remark: превращает [[…]] в ссылки на заметки, неразрешённые — в серый текст. */
export function remarkWikiLinks(options: { links: WikiNoteLink[] }) {
  return (tree: unknown) => {
    transform(tree as MdNode, options.links);
  };
}
