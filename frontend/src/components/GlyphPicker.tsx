import { Label } from "@/components/ui/label";
import { FoodGlyph } from "@/components/FoodGlyph";
import { FOOD_KINDS, FOOD_COLORS } from "@/components/food-kinds";

interface Props {
  title: string;
  kind: string;
  color: string;
  onKindChange: (kind: string) => void;
  onColorChange: (color: string) => void;
}

export function GlyphPicker({ title, kind, color, onKindChange, onColorChange }: Readonly<Props>) {
  return (
    <div className="space-y-2">
      <Label>Иконка</Label>
      <div className="flex flex-wrap items-start gap-4">
        <div className="w-32 shrink-0 overflow-hidden rounded-md border border-border">
          <FoodGlyph title={title} kind={kind || null} color={color || null} />
        </div>
        <div className="flex-1 min-w-[200px] space-y-2">
          <div className="space-y-1">
            <Label htmlFor="glyph-kind" className="text-xs">
              Тип
            </Label>
            <select
              id="glyph-kind"
              value={kind}
              onChange={(e) => onKindChange(e.target.value)}
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
            >
              <option value="">— Авто (по названию) —</option>
              {FOOD_KINDS.map((k) => (
                <option key={k.id} value={k.id}>
                  {k.label}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Цвет</Label>
            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => onColorChange("")}
                aria-label="Авто-цвет"
                title="Авто (по названию)"
                className={`h-7 w-7 rounded-full border-2 text-xs ${
                  color === "" ? "border-foreground" : "border-border"
                }`}
              >
                ↺
              </button>
              {(Object.keys(FOOD_COLORS) as Array<keyof typeof FOOD_COLORS>).map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => onColorChange(c)}
                  aria-label={c}
                  title={c}
                  style={{ background: FOOD_COLORS[c].dk }}
                  className={`h-7 w-7 rounded-full border-2 ${
                    color === c ? "border-foreground" : "border-transparent"
                  }`}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
