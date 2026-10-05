import { type FormEvent, Suspense, useState } from "react";
import { Link, Outlet, useMatch, useNavigate, useSearchParams } from "react-router-dom";
import { useAuthStore } from "@/store/auth";
import { useLogout } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";
import { mainSiteUrl } from "@/lib/wikiHost";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { WolfMark } from "@/components/WolfMark";
import { NotebookTree } from "./NotebookTree";
import { WikiLoading } from "./WikiStatus";
import { useWikiNote, useWikiNotebooks } from "./hooks";
import { searchPath } from "./paths";

/** Блокнот, который подсветить в дереве: открытый блокнот или блокнот открытой заметки. */
function useActiveNotebookId(): string | null {
  const notebookId = useMatch("/b/:notebookId")?.params.notebookId;
  const noteSlug = useMatch("/n/*")?.params["*"];
  // Тот же ключ запроса, что у страницы заметки: при успехе второго обращения к API нет
  const { data: note } = useWikiNote(noteSlug || undefined);
  return notebookId ?? note?.notebook?.id ?? null;
}

function SearchBox({ initial }: Readonly<{ initial: string }>) {
  const navigate = useNavigate();
  const [value, setValue] = useState(initial);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    navigate(searchPath({ q: value.trim() }));
  };

  return (
    <form onSubmit={handleSubmit} role="search" className="flex min-w-0 flex-1 gap-2 md:max-w-md">
      <Input
        type="search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Поиск по заметкам"
        aria-label="Поиск по заметкам"
        maxLength={200}
      />
      <Button type="submit" variant="outline" size="sm" className="shrink-0">
        Найти
      </Button>
    </form>
  );
}

export function WikiLayout() {
  const user = useAuthStore((s) => s.user);
  const logout = useLogout();
  const { theme, toggleTheme } = useTheme();
  const [treeOpen, setTreeOpen] = useState(false);
  const notebooks = useWikiNotebooks();
  const activeNotebookId = useActiveNotebookId();
  const siteUrl = mainSiteUrl();
  // На странице поиска строка в шапке повторяет запрос из адреса
  const onSearchPage = useMatch("/search") !== null;
  const [searchParams] = useSearchParams();
  const headerQuery = onSearchPage ? (searchParams.get("q") ?? "") : "";

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border">
        <div className="container mx-auto px-4 py-3 flex flex-wrap items-center gap-x-4 gap-y-2">
          <div className="flex items-center gap-2 shrink-0">
            <Button
              variant="ghost"
              size="sm"
              className="md:hidden"
              aria-label="Блокноты"
              aria-expanded={treeOpen}
              onClick={() => setTreeOpen((open) => !open)}
            >
              ☰
            </Button>
            <Link to="/" className="flex items-center gap-2">
              <WolfMark size={24} className="text-foreground" />
              <span className="text-xl font-bold">Вики</span>
            </Link>
          </div>

          <div className="order-last w-full md:order-none md:w-auto md:flex-1">
            <SearchBox key={headerQuery} initial={headerQuery} />
          </div>

          <div className="ml-auto flex items-center gap-2 shrink-0">
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "Светлая тема" : "Тёмная тема"}
              title={theme === "dark" ? "Светлая тема" : "Тёмная тема"}
            >
              {theme === "dark" ? "☀" : "☾"}
            </Button>
            {siteUrl && (
              <Button variant="ghost" size="sm" asChild>
                <a href={siteUrl}>На сайт</a>
              </Button>
            )}
            {user && <span className="hidden lg:inline text-sm text-muted-foreground">{user.username}</span>}
            <Button variant="outline" size="sm" onClick={() => logout.mutate()}>
              Выйти
            </Button>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-6 md:flex md:items-start md:gap-8">
        <aside
          data-testid="wiki-sidebar"
          className={cn(
            "mb-6 md:mb-0 md:block md:w-64 md:shrink-0 md:sticky md:top-4 md:max-h-[calc(100vh-2rem)] md:overflow-y-auto",
            !treeOpen && "hidden"
          )}
        >
          <h2 className="mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Блокноты
          </h2>
          {notebooks.isLoading && <WikiLoading />}
          {notebooks.isError && (
            <p className="px-2 text-sm text-muted-foreground">Список блокнотов не загрузился.</p>
          )}
          {notebooks.data && (
            <NotebookTree
              nodes={notebooks.data}
              activeId={activeNotebookId}
              onNavigate={() => setTreeOpen(false)}
            />
          )}
        </aside>

        <main className="min-w-0 flex-1">
          <Suspense fallback={<WikiLoading />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
