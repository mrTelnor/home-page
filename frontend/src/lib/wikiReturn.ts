// Возврат на вики после входа на сайте: адрес приходит из адресной строки (`?next=`),
// поэтому принимается только адрес вики этого же домена — иначе это open redirect.
import { WIKI_PREFIX } from "./wikiHost";

// Пробелы и управляющие символы браузер выбрасывает при разборе адреса, обратный слэш
// считает прямым — в честном адресе возврата их нет, такие значения не разбираем вовсе.
// eslint-disable-next-line no-control-regex -- именно управляющие символы и ищем
const FORBIDDEN_CHARS = /[\u0000- \u007f\\]/;

/**
 * Адрес возврата на вики или null, если значение не ведёт строго на origin вики
 * этого же сайта (`<схема сайта>//wiki.<хост сайта>`). Сравниваются схема и хост
 * разобранного URL, а не подстрока. Результат собирается заново от своего origin:
 * из чужого значения берутся только путь, запрос и якорь.
 */
export function safeWikiReturnUrl(
  raw: string | null | undefined,
  loc: Pick<Location, "protocol" | "host"> = globalThis.location
): string | null {
  if (!raw || FORBIDDEN_CHARS.test(raw)) return null;

  let url: URL;
  try {
    // Без базового адреса: относительные значения (`/path`, `//host`) не принимаются
    url = new URL(raw);
  } catch {
    return null;
  }

  if (loc.protocol !== "https:" && loc.protocol !== "http:") return null;
  if (url.protocol !== loc.protocol) return null;
  // host включает порт: другой порт — другой origin
  if (url.host !== `${WIKI_PREFIX}${loc.host}`) return null;
  if (url.username || url.password) return null;
  // Путь `//host` роутер вики мог бы принять за внешний адрес
  if (url.pathname.startsWith("//")) return null;

  return `${loc.protocol}//${WIKI_PREFIX}${loc.host}${url.pathname}${url.search}${url.hash}`;
}
