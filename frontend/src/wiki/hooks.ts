import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError, api } from "@/api/client";
import { endpoints } from "@/api/endpoints";
import {
  type WikiNoteDetail,
  type WikiNoteSummary,
  type WikiNotebookNode,
} from "@/api/types";
import { isValidWikiSlug } from "@/lib/wikiSlug";
import { type SearchParams } from "./paths";

/** Сколько последних заметок грузим: хватает и для обзора, и для подсказок фильтров поиска. */
export const RECENT_LIMIT = 50;
export const SEARCH_LIMIT = 50;

const STALE_TIME = 1000 * 60 * 5;

// Ответ сервера (401/403/404/429/503) повторять незачем: 503 показываем сразу,
// с кнопкой «Повторить». Один повтор — только на сетевой сбой.
const retry = (count: number, err: unknown) => !(err instanceof ApiError) && count < 1;

export function useWikiNotebooks() {
  return useQuery({
    queryKey: ["wiki", "notebooks"],
    queryFn: () => api.get<WikiNotebookNode[]>(endpoints.wiki.notebooks),
    staleTime: STALE_TIME,
    retry,
  });
}

export function useWikiNotebookNotes(notebookId: string | undefined) {
  return useQuery({
    queryKey: ["wiki", "notebook-notes", notebookId],
    queryFn: () => api.get<WikiNoteSummary[]>(endpoints.wiki.notebookNotes(notebookId ?? "")),
    enabled: Boolean(notebookId),
    staleTime: STALE_TIME,
    retry,
  });
}

export function useWikiNote(slug: string | undefined) {
  return useQuery({
    queryKey: ["wiki", "note", slug],
    queryFn: () => api.get<WikiNoteDetail>(endpoints.wiki.note(slug ?? "")),
    // Негодный slug (пустой, с сегментами «.» / «..») на API не уходит
    enabled: isValidWikiSlug(slug),
    staleTime: STALE_TIME,
    retry,
  });
}

export function useWikiRecent() {
  return useQuery({
    queryKey: ["wiki", "recent", RECENT_LIMIT],
    queryFn: () => api.get<WikiNoteSummary[]>(endpoints.wiki.recent(RECENT_LIMIT)),
    staleTime: STALE_TIME,
    retry,
  });
}

export function hasSearchCriteria(params: SearchParams): boolean {
  return Boolean(params.q?.trim() || params.project || params.type || params.tag);
}

export function useWikiSearch(params: SearchParams) {
  return useQuery({
    queryKey: ["wiki", "search", params.q ?? "", params.project ?? "", params.type ?? "", params.tag ?? ""],
    queryFn: () =>
      api.get<WikiNoteSummary[]>(endpoints.wiki.search({ ...params, limit: SEARCH_LIMIT })),
    // Без слов и фильтров бэкенд вернёт пустой список — запрос не делаем
    enabled: hasSearchCriteria(params),
    staleTime: STALE_TIME,
    retry,
  });
}

const WIKI_NAME = "Вики";

export function useWikiTitle(title: string) {
  useEffect(() => {
    document.title = title ? `${title} | ${WIKI_NAME}` : WIKI_NAME;
  }, [title]);
}

/** Найти блокнот в дереве и путь к нему от корня (для «хлебных крошек»). */
export function findNotebookPath(
  tree: WikiNotebookNode[],
  notebookId: string
): WikiNotebookNode[] | null {
  for (const node of tree) {
    if (node.id === notebookId) return [node];
    const nested = findNotebookPath(node.children, notebookId);
    if (nested) return [node, ...nested];
  }
  return null;
}
