import { Link, useParams } from "react-router-dom";
import { NoteList } from "../NoteList";
import { WikiError, WikiLoading } from "../WikiStatus";
import { findNotebookPath, useWikiNotebookNotes, useWikiNotebooks, useWikiTitle } from "../hooks";
import { notebookPath } from "../paths";

export function WikiNotebookPage() {
  const { notebookId } = useParams();
  const notebooks = useWikiNotebooks();
  const notes = useWikiNotebookNotes(notebookId);

  const trail = notebooks.data && notebookId ? findNotebookPath(notebooks.data, notebookId) : null;
  const notebook = trail?.at(-1) ?? null;
  useWikiTitle(notebook?.name ?? "Блокнот");

  if (notes.error) {
    return (
      <WikiError
        error={notes.error}
        onRetry={() => void notes.refetch()}
        notFoundTitle="Блокнот не найден"
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <nav
          aria-label="Путь"
          className="flex flex-wrap items-center gap-1 text-sm text-muted-foreground"
        >
          <Link to="/" className="hover:text-primary hover:underline">
            База знаний
          </Link>
          {trail?.slice(0, -1).map((node) => (
            <span key={node.id} className="flex items-center gap-1">
              <span aria-hidden="true">/</span>
              <Link to={notebookPath(node.id)} className="hover:text-primary hover:underline">
                {node.name}
              </Link>
            </span>
          ))}
        </nav>
        <h1 className="text-3xl font-bold">{notebook?.name ?? "Блокнот"}</h1>
      </div>

      {notebook && notebook.children.length > 0 && (
        <section className="space-y-2" aria-labelledby="wiki-children">
          <h2 id="wiki-children" className="text-xl font-semibold">
            Вложенные блокноты
          </h2>
          <ul className="flex flex-wrap gap-2">
            {notebook.children.map((child) => (
              <li key={child.id}>
                <Link
                  to={notebookPath(child.id)}
                  className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-1.5 text-sm hover:bg-accent"
                >
                  {child.name}
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {child.total_note_count}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="space-y-2" aria-labelledby="wiki-notebook-notes">
        <h2 id="wiki-notebook-notes" className="text-xl font-semibold">
          Заметки
        </h2>
        {notes.isLoading && <WikiLoading />}
        {notes.data && <NoteList notes={notes.data} emptyText="В самом блокноте заметок нет." />}
      </section>
    </div>
  );
}
