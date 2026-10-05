import { lazy, useEffect } from "react";
import { Link, Route, Routes } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { WikiGate } from "./WikiGate";
import { WikiLayout } from "./WikiLayout";
import { StatusBox } from "./WikiStatus";
import { useWikiTitle } from "./hooks";

// Страницы — отдельными чанками; разбор Markdown и подсветка кода нужны только заметке
const WikiHomePage = lazy(() => import("./pages/WikiHomePage").then((m) => ({ default: m.WikiHomePage })));
const WikiNotebookPage = lazy(() => import("./pages/WikiNotebookPage").then((m) => ({ default: m.WikiNotebookPage })));
const WikiNotePage = lazy(() => import("./pages/WikiNotePage").then((m) => ({ default: m.WikiNotePage })));
const WikiSearchPage = lazy(() => import("./pages/WikiSearchPage").then((m) => ({ default: m.WikiSearchPage })));
const WikiLoginPage = lazy(() => import("./pages/WikiLoginPage").then((m) => ({ default: m.WikiLoginPage })));

/** Вики закрытая: просим поисковики её не индексировать. */
function useNoIndex() {
  useEffect(() => {
    const meta = document.createElement("meta");
    meta.name = "robots";
    meta.content = "noindex, nofollow";
    document.head.appendChild(meta);
    return () => meta.remove();
  }, []);
}

function WikiNotFound() {
  useWikiTitle("Страница не найдена");
  return (
    <StatusBox
      title="Страница не найдена"
      action={
        <Button asChild variant="outline">
          <Link to="/">К обзору</Link>
        </Button>
      }
    />
  );
}

/** Маршруты вики: показываются с корня на хосте wiki.<domain> (см. lib/wikiHost). */
export default function WikiApp() {
  useNoIndex();
  return (
    <Routes>
      <Route path="/login" element={<WikiLoginPage />} />
      <Route element={<WikiGate />}>
        <Route element={<WikiLayout />}>
          <Route path="/" element={<WikiHomePage />} />
          <Route path="/b/:notebookId" element={<WikiNotebookPage />} />
          <Route path="/n/*" element={<WikiNotePage />} />
          <Route path="/search" element={<WikiSearchPage />} />
          <Route path="*" element={<WikiNotFound />} />
        </Route>
      </Route>
    </Routes>
  );
}
