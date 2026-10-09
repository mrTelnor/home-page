// Адреса страниц вики (внутри SPA на хосте wiki.<domain>).
import { mainSiteUrl } from "@/lib/wikiHost";

/** Страница заметки: `/n/<slug>`, слэши slug остаются слэшами пути. */
export function notePath(slug: string): string {
  return `/n/${slug.split("/").map(encodeURIComponent).join("/")}`;
}

export function notebookPath(notebookId: string): string {
  return `/b/${encodeURIComponent(notebookId)}`;
}

export interface SearchParams {
  q?: string;
  project?: string;
  type?: string;
  tag?: string;
}

export function searchPath(params: SearchParams = {}): string {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.project) query.set("project", params.project);
  if (params.type) query.set("type", params.type);
  if (params.tag) query.set("tag", params.tag);
  const qs = query.toString();
  return qs ? `/search?${qs}` : "/search";
}

/**
 * Страница вики, на которую вернуть после входа. Своей страницы входа у вики нет:
 * `/login` (туда ведёт общий выход из аккаунта и старые ссылки) заменяется корнем.
 */
export function wikiReturnPath(location: {
  pathname: string;
  search: string;
  hash: string;
}): string {
  if (location.pathname === "/login") return "/";
  return location.pathname + location.search + location.hash;
}

/**
 * Вход — на основном сайте: адрес его страницы входа с возвратом на страницу вики.
 * Сайт принимает возврат только на origin вики своего домена (lib/wikiReturn).
 * null — вики открыта не на поддомене `wiki.` (локально через VITE_WIKI), адрес сайта неизвестен.
 */
export function siteLoginUrl(
  returnPath: string,
  loc: Pick<Location, "protocol" | "host"> = globalThis.location
): string | null {
  const site = mainSiteUrl(loc);
  if (!site) return null;
  const back = `${loc.protocol}//${loc.host}${returnPath}`;
  return `${site}/login?next=${encodeURIComponent(back)}`;
}
