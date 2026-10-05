import { useState } from "react";
import { Link } from "react-router-dom";
import { type WikiNotebookNode } from "@/api/types";
import { cn } from "@/lib/utils";
import { notebookPath } from "./paths";

interface NotebookTreeProps {
  nodes: WikiNotebookNode[];
  activeId?: string | null;
  onNavigate?: () => void;
}

/** Дерево блокнотов. Дерево небольшое — по умолчанию раскрыто целиком, ветки можно свернуть. */
export function NotebookTree({ nodes, activeId = null, onNavigate }: Readonly<NotebookTreeProps>) {
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(new Set());

  const toggle = (id: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const renderNodes = (items: WikiNotebookNode[], depth: number) => (
    <ul className={cn("space-y-0.5", depth > 0 && "ml-3 border-l border-border pl-2")}>
      {items.map((node) => {
        const hasChildren = node.children.length > 0;
        const isCollapsed = collapsed.has(node.id);
        return (
          <li key={node.id}>
            <div className="flex items-center gap-1">
              {hasChildren ? (
                <button
                  type="button"
                  onClick={() => toggle(node.id)}
                  aria-expanded={!isCollapsed}
                  aria-label={`${isCollapsed ? "Развернуть" : "Свернуть"} «${node.name}»`}
                  className="size-6 shrink-0 rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
                >
                  {isCollapsed ? "▸" : "▾"}
                </button>
              ) : (
                <span className="size-6 shrink-0" aria-hidden="true" />
              )}
              <Link
                to={notebookPath(node.id)}
                onClick={onNavigate}
                aria-current={node.id === activeId ? "page" : undefined}
                className={cn(
                  "flex min-w-0 flex-1 items-center justify-between gap-2 rounded-md px-2 py-1 text-sm hover:bg-accent",
                  node.id === activeId
                    ? "bg-accent font-semibold text-foreground"
                    : "text-foreground/80 hover:text-foreground"
                )}
              >
                <span className="truncate">{node.name}</span>
                <span className="text-xs text-muted-foreground tabular-nums">
                  {node.total_note_count}
                </span>
              </Link>
            </div>
            {hasChildren && !isCollapsed && renderNodes(node.children, depth + 1)}
          </li>
        );
      })}
    </ul>
  );

  return <nav aria-label="Блокноты">{renderNodes(nodes, 0)}</nav>;
}
