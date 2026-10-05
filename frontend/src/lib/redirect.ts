/**
 * Переход на другой origin (сайт ↔ вики). Делается явно, мимо роутера: адрес к этому
 * моменту уже собран или проверен нашим кодом (см. lib/wikiReturn, wiki/paths).
 * `replace` — чтобы кнопка «назад» не возвращала на промежуточную страницу.
 */
export function redirectTo(url: string): void {
  globalThis.location.replace(url);
}
