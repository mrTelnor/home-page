import { type FormEvent, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { type WikiNoteSummary } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NoteList } from "../NoteList";
import { WikiError, WikiLoading } from "../WikiStatus";
import { metaString } from "../format";
import { SEARCH_LIMIT, hasSearchCriteria, useWikiRecent, useWikiSearch, useWikiTitle } from "../hooks";
import { type SearchParams, searchPath } from "../paths";

const FILTER_MAX_LENGTH = 100;

interface FilterOptions {
  projects: string[];
  types: string[];
  tags: string[];
}

/**
 * Подсказки для фильтров. Отдельного списка значений в API нет, поэтому собираем их
 * из уже загруженных заметок (последние изменённые и текущая выдача). Это подсказки,
 * а не полный перечень: значение можно ввести и вручную.
 */
function collectOptions(notes: WikiNoteSummary[]): FilterOptions {
  const projects = new Set<string>();
  const types = new Set<string>();
  const tags = new Set<string>();
  for (const note of notes) {
    const project = metaString(note.metadata, "project");
    const type = metaString(note.metadata, "type");
    if (project) projects.add(project);
    if (type) types.add(type);
    for (const tag of note.tags) tags.add(tag);
  }
  const sorted = (set: Set<string>) => [...set].sort((a, b) => a.localeCompare(b, "ru"));
  return { projects: sorted(projects), types: sorted(types), tags: sorted(tags) };
}

interface FilterFieldProps {
  id: string;
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}

function FilterField({ id, label, value, options, onChange }: Readonly<FilterFieldProps>) {
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        list={`${id}-options`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        maxLength={FILTER_MAX_LENGTH}
        placeholder="любой"
        autoComplete="off"
      />
      <datalist id={`${id}-options`}>
        {options.map((option) => (
          <option key={option} value={option} />
        ))}
      </datalist>
    </div>
  );
}

interface SearchFormProps {
  initial: SearchParams;
  options: FilterOptions;
}

function SearchForm({ initial, options }: Readonly<SearchFormProps>) {
  const navigate = useNavigate();
  const [q, setQ] = useState(initial.q ?? "");
  const [project, setProject] = useState(initial.project ?? "");
  const [type, setType] = useState(initial.type ?? "");
  const [tag, setTag] = useState(initial.tag ?? "");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    navigate(
      searchPath({ q: q.trim(), project: project.trim(), type: type.trim(), tag: tag.trim() })
    );
  };

  return (
    <form onSubmit={handleSubmit} className="rounded-xl border border-border bg-card p-4 space-y-3">
      <div className="space-y-1">
        <Label htmlFor="wiki-q">Слова</Label>
        <Input
          id="wiki-q"
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          maxLength={200}
          placeholder="Ищет по началу слова"
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <FilterField id="wiki-project" label="Проект" value={project} options={options.projects} onChange={setProject} />
        <FilterField id="wiki-type" label="Тип" value={type} options={options.types} onChange={setType} />
        <FilterField id="wiki-tag" label="Тег" value={tag} options={options.tags} onChange={setTag} />
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="submit">Найти</Button>
        <Button type="button" variant="outline" onClick={() => navigate(searchPath())}>
          Сбросить
        </Button>
      </div>
    </form>
  );
}

export function WikiSearchPage() {
  useWikiTitle("Поиск");
  const [urlParams] = useSearchParams();
  const params: SearchParams = {
    q: urlParams.get("q") ?? undefined,
    project: urlParams.get("project") ?? undefined,
    type: urlParams.get("type") ?? undefined,
    tag: urlParams.get("tag") ?? undefined,
  };
  const active = hasSearchCriteria(params);
  const search = useWikiSearch(params);
  const recent = useWikiRecent();

  const options = useMemo(
    () => collectOptions([...(recent.data ?? []), ...(search.data ?? [])]),
    [recent.data, search.data]
  );

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Поиск</h1>
      {/* key — чтобы форма перечитала значения при переходе по ссылке-бейджу или «назад» */}
      <SearchForm key={urlParams.toString()} initial={params} options={options} />

      {!active && (
        <p className="text-muted-foreground">Введите слова или выберите фильтр — проект, тип или тег.</p>
      )}
      {active && search.isLoading && <WikiLoading />}
      {active && search.isError && (
        <WikiError error={search.error} onRetry={() => void search.refetch()} notFoundTitle="Запрос не принят" />
      )}
      {active && search.data && (
        <section className="space-y-2" aria-labelledby="wiki-results">
          <h2 id="wiki-results" className="text-xl font-semibold">
            Найдено: {search.data.length}
            {search.data.length === SEARCH_LIMIT && (
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                показаны первые {SEARCH_LIMIT} — уточните запрос
              </span>
            )}
          </h2>
          <NoteList notes={search.data} emptyText="Ничего не найдено." />
        </section>
      )}
    </div>
  );
}
