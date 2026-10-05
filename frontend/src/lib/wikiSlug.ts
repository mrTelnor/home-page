// Проверка slug заметки вики — одна на построение пути API и на страницу заметки.

/**
 * Slug годится для запроса, если в нём нет пустых сегментов и сегментов «.» / «..»:
 * браузер схлопывает их в адресе (в том числе записанные как %2E), и запрос
 * `/api/wiki/notes/../../auth/me` ушёл бы на чужой эндпоинт.
 */
export function isValidWikiSlug(slug: string | null | undefined): slug is string {
  if (!slug) return false;
  return slug.split("/").every((segment) => segment !== "" && segment !== "." && segment !== "..");
}
