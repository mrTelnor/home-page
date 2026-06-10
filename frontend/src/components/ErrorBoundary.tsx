import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Необработанная ошибка интерфейса:", error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-background flex items-center justify-center px-4">
          <div className="max-w-md w-full rounded-lg border border-border bg-card p-8 text-center space-y-4">
            <h1 className="text-2xl font-bold text-foreground">Что-то пошло не так</h1>
            <p className="text-muted-foreground text-sm">
              Произошла непредвиденная ошибка. Попробуйте перезагрузить страницу — обычно это
              помогает.
            </p>
            <Button onClick={this.handleReload} className="w-full">
              Перезагрузить
            </Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
