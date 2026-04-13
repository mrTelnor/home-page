import { useEffect, useRef } from "react";
import { useTelegramVerify, type TelegramAuthData } from "@/hooks/useProfile";

const BOT_USERNAME = import.meta.env.VITE_TELEGRAM_BOT_USERNAME || "dinnervote_bot";

declare global {
  interface Window {
    onTelegramAuth?: (user: TelegramAuthData) => void;
  }
}

export function TelegramLoginButton() {
  const containerRef = useRef<HTMLDivElement>(null);
  const verify = useTelegramVerify();

  useEffect(() => {
    window.onTelegramAuth = (user) => {
      verify.mutate(user);
    };

    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.setAttribute("data-telegram-login", BOT_USERNAME);
    script.setAttribute("data-size", "medium");
    script.setAttribute("data-onauth", "onTelegramAuth(user)");
    script.setAttribute("data-request-access", "write");

    containerRef.current?.appendChild(script);

    return () => {
      delete window.onTelegramAuth;
    };
  }, [verify]);

  return (
    <div>
      <div ref={containerRef} />
      {verify.isError && (
        <p className="text-sm text-destructive mt-2">
          Ошибка привязки. Попробуйте ещё раз.
        </p>
      )}
    </div>
  );
}
