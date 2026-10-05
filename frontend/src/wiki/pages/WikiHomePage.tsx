import { Link } from "react-router-dom";
import { NoteList } from "../NoteList";
import { WikiError, WikiLoading } from "../WikiStatus";
import { useWikiNotebooks, useWikiRecent, useWikiTitle } from "../hooks";
import { notebookPath } from "../paths";

const RECENT_SHOWN = 20;

export function WikiHomePage() {
  useWikiTitle("");
  const notebooks = useWikiNotebooks();
  const recent = useWikiRecent();

  // Блокноты и «последние» падают вместе (общая база) — одно сообщение вместо двух
  const error = notebooks.error ?? recent.error;
  if (error) {
    return (
      <WikiError
        error={error}
        onRetry={() => {
          void notebooks.refetch();
          void recent.refetch();
        }}
      />
    );
  }

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold">База знаний</h1>

      <section className="space-y-3" aria-labelledby="wiki-notebooks">
        <h2 id="wiki-notebooks" className="text-xl font-semibold">
          Блокноты
        </h2>
        {notebooks.isLoading && <WikiLoading />}
        {notebooks.data && notebooks.data.length === 0 && (
          <p className="text-muted-foreground">Блокнотов пока нет.</p>
        )}
        {notebooks.data && notebooks.data.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2">
            {notebooks.data.map((root) => (
              <div key={root.id} className="rounded-xl border border-border bg-card p-4 space-y-2">
                <div className="flex items-baseline justify-between gap-2">
                  <Link
                    to={notebookPath(root.id)}
                    className="text-lg font-semibold hover:text-primary hover:underline"
                  >
                    {root.name}
                  </Link>
                  <span className="text-xs text-muted-foreground shrink-0">
                    заметок: {root.total_note_count}
                  </span>
                </div>
                {root.children.length > 0 && (
                  <ul className="space-y-1 text-sm">
                    {root.children.map((child) => (
                      <li key={child.id} className="flex items-baseline justify-between gap-2">
                        <Link
                          to={notebookPath(child.id)}
                          className="text-foreground/80 hover:text-primary hover:underline"
                        >
                          {child.name}
                        </Link>
                        <span className="text-xs text-muted-foreground tabular-nums">
                          {child.total_note_count}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3" aria-labelledby="wiki-recent">
        <h2 id="wiki-recent" className="text-xl font-semibold">
          Последние изменения
        </h2>
        {recent.isLoading && <WikiLoading />}
        {recent.data && (
          <NoteList notes={recent.data.slice(0, RECENT_SHOWN)} emptyText="Заметок пока нет." />
        )}
      </section>
    </div>
  );
}
