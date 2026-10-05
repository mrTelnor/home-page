// Один бандл обслуживает и сайт рецептов, и вики: набор маршрутов выбирается по имени хоста.

const WIKI_PREFIX = "wiki.";

/**
 * Вики показывается на хосте `wiki.<domain>` (на проде — второй роутер на тот же контейнер).
 * Для локальной разработки без поддомена — переменная сборки `VITE_WIKI=true`.
 */
export function isWikiHost(hostname: string = globalThis.location?.hostname ?? ""): boolean {
  if (import.meta.env.VITE_WIKI === "true") return true;
  return hostname.toLowerCase().startsWith(WIKI_PREFIX);
}

/** Адрес сайта рецептов для ссылки из вики; null — если вики открыта не на поддомене `wiki.`. */
export function mainSiteUrl(loc: Pick<Location, "protocol" | "host"> = globalThis.location): string | null {
  if (!loc.host.toLowerCase().startsWith(WIKI_PREFIX)) return null;
  return `${loc.protocol}//${loc.host.slice(WIKI_PREFIX.length)}`;
}
