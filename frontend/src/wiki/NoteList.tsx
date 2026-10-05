import { Link } from "react-router-dom";
import { type WikiNoteSummary } from "@/api/types";
import { NoteBadges } from "./NoteMeta";
import { formatDateTime } from "./format";
import { notePath } from "./paths";

interface NoteListProps {
  notes: WikiNoteSummary[];
  emptyText: string;
}

export function NoteList({ notes, emptyText }: Readonly<NoteListProps>) {
  if (notes.length === 0) {
    return <p className="text-muted-foreground">{emptyText}</p>;
  }
  return (
    <ul className="divide-y divide-border rounded-xl border border-border bg-card">
      {notes.map((note) => (
        <li key={note.id} className="p-3 sm:p-4 space-y-1.5">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <Link
              to={notePath(note.slug)}
              className="text-base font-semibold text-foreground hover:text-primary hover:underline"
            >
              {note.title}
            </Link>
            <time dateTime={note.updated_at} className="text-xs text-muted-foreground shrink-0">
              {formatDateTime(note.updated_at)}
            </time>
          </div>
          <p className="font-mono text-xs text-muted-foreground break-all">{note.slug}</p>
          <NoteBadges metadata={note.metadata} tags={note.tags} />
        </li>
      ))}
    </ul>
  );
}
