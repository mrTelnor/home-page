import { useEffect, useRef } from "react";
import { useTelegramVerify, type TelegramAuthData } from "@/hooks/useProfile";

const BOT_USERNAME = import.meta.env.VITE_TELEGRAM_BOT_USERNAME || "dinnervote_bot";

declare global {
  // eslint-disable-next-line no-var
  var onTelegramAuth: ((user: TelegramAuthData) => void) | undefined;
}

export function TelegramLoginButton() {
  const containerRef = useRef<HTMLDivElement>(null);
  const verify = useTelegramVerify();
  // mutate в react-query v5 стабилен между рендерами, поэтому эффект отработает
  // один раз — виджет монтируется единожды, без накопления <script>
  const mutate = verify.mutate;

  useEffect(() => {
    globalThis.onTelegramAuth = (user) => {
      mutate(user);
    };

    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.dataset.telegramLogin = BOT_USERNAME;
    script.dataset.size = "medium";
    script.dataset.onauth = "onTelegramAuth(user)";
    script.dataset.requestAccess = "write";

    const container = containerRef.current;
    container?.appendChild(script);

    return () => {
      globalThis.onTelegramAuth = undefined;
      script.remove(); // не копим <script> при перемонтировании
    };
  }, [mutate]);

  return (
    <div>
      <div ref={containerRef} />
      {verify.isError && (
        <p className="text-sm text-destructive mt-2">Ошибка привязки. Попробуйте ещё раз.</p>
      )}
    </div>
  );
}
