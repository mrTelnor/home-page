import { type ComponentProps } from "react";
import { Link } from "react-router-dom";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { common } from "lowlight";
import dockerfile from "highlight.js/lib/languages/dockerfile";
import powershell from "highlight.js/lib/languages/powershell";
import { type WikiNoteLink } from "@/api/types";
import { remarkWikiLinks } from "./wikiLinks";
import "./wiki.css";

// Набор common не содержит powershell и dockerfile, а в заметках они встречаются.
// Неизвестный язык блока не ошибка: такой блок остаётся без подсветки.
const languages = { ...common, dockerfile, powershell };

/** Ссылка внутри вики (`/n/…`) — переход без перезагрузки; внешняя — в новой вкладке. */
function MarkdownLink({ href, children, className, title }: ComponentProps<"a">) {
  if (href?.startsWith("/") && !href.startsWith("//")) {
    return (
      <Link to={href} className={className} title={title}>
        {children}
      </Link>
    );
  }
  if (href?.startsWith("#")) {
    return (
      <a href={href} className={className} title={title}>
        {children}
      </a>
    );
  }
  return (
    <a
      href={href}
      className={className}
      title={title}
      target="_blank"
      rel="noopener noreferrer nofollow"
    >
      {children}
    </a>
  );
}

// Из пропсов берём только нужное: служебный `node` (узел дерева) в DOM не передаём
const components: Components = {
  a: ({ href, className, title, children }) => (
    <MarkdownLink href={href} className={className} title={title}>
      {children}
    </MarkdownLink>
  ),
  // Широкая таблица прокручивается сама, а не растягивает страницу на телефоне
  table: ({ children }) => (
    <div className="wiki-md-table">
      <table>{children}</table>
    </div>
  ),
  img: ({ src, alt, title }) => (
    <img src={src} alt={alt ?? ""} title={title} loading="lazy" referrerPolicy="no-referrer" />
  ),
};

interface MarkdownProps {
  content: string;
  /** Исходящие ссылки заметки — по ним разрешаются [[…]] */
  links?: WikiNoteLink[];
}

const NO_LINKS: WikiNoteLink[] = [];

/**
 * Текст заметки. Сырой HTML не исполняется: rehype-raw не подключён, поэтому теги
 * из заметки выводятся как обычный текст; опасные схемы ссылок (javascript:) срезает
 * сам react-markdown.
 */
export function Markdown({ content, links = NO_LINKS }: Readonly<MarkdownProps>) {
  return (
    <div className="wiki-md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, [remarkWikiLinks, { links }]]}
        rehypePlugins={[[rehypeHighlight, { languages }]]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
