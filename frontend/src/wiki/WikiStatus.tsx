import { type ReactNode, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/button";
import { siteLoginUrl, wikiReturnPath } from "./paths";

interface StatusBoxProps {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}

export function StatusBox({ title, children, action }: Readonly<StatusBoxProps>) {
  return (
    <div className="rounded-xl border border-border bg-card p-6 text-center space-y-3 max-w-xl mx-auto">
      <h2 className="text-xl font-bold">{title}</h2>
      {children && <p className="text-sm text-muted-foreground">{children}</p>}
      {action}
    </div>
  );
}

export function WikiLoading() {
  return <p className="text-muted-foreground">Загрузка...</p>;
}

/**
 * API ответил 401 посреди работы (сессия истекла или завершена на сайте): перечитываем
 * «кто я» — гейт вики увидит гостя и сам отправит на вход с возвратом на эту страницу.
 */
function SessionExpired() {
  const queryClient = useQueryClient();
  const loginUrl = siteLoginUrl(wikiReturnPath(useLocation()));
  useEffect(() => {
    void queryClient.invalidateQueries({ queryKey: ["me"] });
  }, [queryClient]);
  return (
    <StatusBox
      title="Сессия закончилась"
      action={
        loginUrl && (
          <Button asChild>
            <a href={loginUrl}>Войти</a>
          </Button>
        )
      }
    >
      Войдите заново, чтобы продолжить.
    </StatusBox>
  );
}

interface WikiErrorProps {
  error: unknown;
  onRetry?: () => void;
  /** Текст для 404 — зависит от того, что искали */
  notFoundTitle?: string;
}

/** Понятное состояние вместо данных: 503 — база знаний недоступна, 404, 429, отказ в доступе. */
export function WikiError({
  error,
  onRetry,
  notFoundTitle = "Не найдено",
}: Readonly<WikiErrorProps>) {
  const status = error instanceof ApiError ? error.status : null;
  const retryButton = onRetry && (
    <Button variant="outline" onClick={onRetry}>
      Повторить
    </Button>
  );

  if (status === 503) {
    return (
      <StatusBox title="База знаний недоступна" action={retryButton}>
        Не удалось получить данные из базы знаний: она на паузе, недоступна или вики выключена.
        Попробуйте позже.
      </StatusBox>
    );
  }
  if (status === 404 || status === 422) {
    return (
      <StatusBox
        title={notFoundTitle}
        action={
          <Button asChild variant="outline">
            <Link to="/">К обзору</Link>
          </Button>
        }
      />
    );
  }
  if (status === 429) {
    return (
      <StatusBox title="Слишком много запросов" action={retryButton}>
        Подождите минуту и повторите.
      </StatusBox>
    );
  }
  if (status === 401) return <SessionExpired />;
  if (status === 403) {
    return <StatusBox title="Нет доступа">Вики доступна только администраторам.</StatusBox>;
  }
  return (
    <StatusBox title="Ошибка загрузки" action={retryButton}>
      Не удалось загрузить данные. Проверьте соединение и повторите.
    </StatusBox>
  );
}
