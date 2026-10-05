// Адреса страниц вики (внутри SPA на хосте wiki.<domain>).

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

// eslint-disable-next-line no-control-regex -- именно управляющие символы и ищем
const CONTROL_CHARS = /[\u0000-\u001f\u007f]/;

/**
 * Куда вернуть после входа. Принимаем только путь внутри вики: значение приходит
 * из адресной строки, внешний адрес (`//host`, `/\host`, `https://…`) и значения
 * с управляющими символами не допускаются.
 */
export function safeNextPath(raw: string | null | undefined): string {
  if (!raw?.startsWith("/")) return "/";
  // Управляющие символы браузер выбрасывает при разборе адреса: «/\t/host» стал бы «//host»
  if (CONTROL_CHARS.test(raw)) return "/";
  if (raw.startsWith("//") || raw.startsWith("/\\")) return "/";
  if (raw === "/login" || raw.startsWith("/login?")) return "/";
  return raw;
}

export function loginPath(next: string): string {
  const safe = safeNextPath(next);
  return safe === "/" ? "/login" : `/login?next=${encodeURIComponent(safe)}`;
}
