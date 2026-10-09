import { Link, useParams } from "react-router-dom";
import { ApiError } from "@/api/client";
import { isValidWikiSlug } from "@/lib/wikiSlug";
import { Markdown } from "../Markdown";
import { NoteBadges } from "../NoteMeta";
import { WikiError, WikiLoading } from "../WikiStatus";
import { formatDateTime } from "../format";
import { useWikiNote, useWikiTitle } from "../hooks";
import { notePath, notebookPath } from "../paths";

// Заметки обычно начинаются со своего заголовка «# …» — тогда отдельный заголовок страницы не нужен
const STARTS_WITH_H1 = /^\s*#\s+\S/;

const NOT_FOUND = new ApiError(404, "Note not found");

export function WikiNotePage() {
  const slug = useParams()["*"] || undefined;
  const { data: note, isLoading, error, refetch } = useWikiNote(slug);
  useWikiTitle(note?.title ?? "Заметка");

  // Негодный slug не запрашиваем; ответ, не похожий на заметку, не показываем
  if (!isValidWikiSlug(slug) || (note && typeof note.content !== "string")) {
    return <WikiError error={NOT_FOUND} notFoundTitle="Заметка не найдена" />;
  }
  if (error) {
    return (
      <WikiError error={error} onRetry={() => void refetch()} notFoundTitle="Заметка не найдена" />
    );
  }
  if (isLoading || !note) return <WikiLoading />;
  const links = Array.isArray(note.links) ? note.links : [];
  const backlinks = Array.isArray(note.backlinks) ? note.backlinks : [];
  const tags = Array.isArray(note.tags) ? note.tags : [];

  return (
    <article className="space-y-6">
      <header className="space-y-3">
        <nav
          aria-label="Путь"
          className="flex flex-wrap items-center gap-1 text-sm text-muted-foreground"
        >
          <Link to="/" className="hover:text-primary hover:underline">
            База знаний
          </Link>
          {note.notebook && (
            <>
              <span aria-hidden="true">/</span>
              <Link
                to={notebookPath(note.notebook.id)}
                className="hover:text-primary hover:underline"
              >
                {note.notebook.name}
              </Link>
            </>
          )}
        </nav>
        {!STARTS_WITH_H1.test(note.content) && <h1 className="text-3xl font-bold">{note.title}</h1>}
        <NoteBadges metadata={note.metadata ?? {}} tags={tags} />
        <p className="text-xs text-muted-foreground">
          <span className="font-mono break-all">{note.slug}</span>
          {" · изменена "}
          <time dateTime={note.updated_at}>{formatDateTime(note.updated_at)}</time>
        </p>
      </header>

      <Markdown content={note.content} links={links} />

      <section className="space-y-2 border-t border-border pt-4" aria-labelledby="wiki-backlinks">
        <h2 id="wiki-backlinks" className="text-lg font-semibold">
          Обратные ссылки
        </h2>
        {backlinks.length === 0 ? (
          <p className="text-sm text-muted-foreground">На эту заметку пока никто не ссылается.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {backlinks.map((link) => (
              <li key={`${link.slug}|${link.alias ?? ""}`}>
                <Link to={notePath(link.slug)} className="text-primary hover:underline">
                  {link.title}
                </Link>
                {link.alias && <span className="text-muted-foreground"> — «{link.alias}»</span>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </article>
  );
}
