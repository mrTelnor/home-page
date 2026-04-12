import { useAuthStore } from "@/store/auth";
import { usePageTitle } from "@/hooks/usePageTitle";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

export function HomePage() {
  usePageTitle("Главная");
  const user = useAuthStore((s) => s.user);

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold">
        Привет, {user?.username}!
      </h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <Card className="cursor-pointer hover:shadow-lg transition-shadow opacity-60">
          <CardHeader>
            <CardTitle>Голосование за ужин</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">Скоро</p>
          </CardContent>
        </Card>
        <Card className="cursor-pointer hover:shadow-lg transition-shadow opacity-60">
          <CardHeader>
            <CardTitle>Рецепты</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">Скоро</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
