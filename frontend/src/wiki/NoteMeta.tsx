import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { metaString } from "./format";
import { searchPath } from "./paths";

interface NoteBadgesProps {
  metadata: Record<string, unknown>;
  tags: string[];
}

/** Бейджи type / status / project и теги. type, project и теги ведут в поиск с этим фильтром. */
export function NoteBadges({ metadata, tags }: Readonly<NoteBadgesProps>) {
  const type = metaString(metadata, "type");
  const status = metaString(metadata, "status");
  const project = metaString(metadata, "project");

  if (!type && !status && !project && tags.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {type && (
        <Badge asChild title="Тип заметки">
          <Link to={searchPath({ type })}>{type}</Link>
        </Badge>
      )}
      {status && (
        <Badge variant="outline" title="Статус">
          {status}
        </Badge>
      )}
      {project && (
        <Badge asChild variant="secondary" title="Проект">
          <Link to={searchPath({ project })}>{project}</Link>
        </Badge>
      )}
      {tags.map((tag) => (
        <Badge key={tag} asChild variant="ghost" className="text-muted-foreground" title="Тег">
          <Link to={searchPath({ tag })}>#{tag}</Link>
        </Badge>
      ))}
    </div>
  );
}
