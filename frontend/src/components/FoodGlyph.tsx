export const FOOD_COLORS = {
  red:    { bg: "#F6D7CF", fg: "#7A2416", dk: "#B8442A" },
  orange: { bg: "#F7DFC2", fg: "#80441A", dk: "#C48A2A" },
  yellow: { bg: "#F6E9B8", fg: "#6E5412", dk: "#B89028" },
  green:  { bg: "#D8E0BC", fg: "#3F5528", dk: "#6B7A4B" },
  teal:   { bg: "#C2DCD6", fg: "#1F4A42", dk: "#3F7268" },
  blue:   { bg: "#C8D5E2", fg: "#1F3A58", dk: "#3F5E86" },
  purple: { bg: "#DACCE0", fg: "#3F2E4C", dk: "#6E5184" },
  pink:   { bg: "#F0CFD4", fg: "#6E2838", dk: "#A8495F" },
  brown:  { bg: "#DFCBB3", fg: "#48331A", dk: "#7A5A32" },
  cream:  { bg: "#EFE5CE", fg: "#5A4A24", dk: "#8E7538" },
} as const;

export type FoodColor = keyof typeof FOOD_COLORS;

export const FOOD_KINDS = [
  { id: "soup",     label: "Суп" },
  { id: "noodles",  label: "Лапша" },
  { id: "eggs",     label: "Яичница" },
  { id: "pancakes", label: "Блины" },
  { id: "pelmeni",  label: "Пельмени" },
  { id: "pie",      label: "Пирог" },
  { id: "pizza",    label: "Пицца" },
  { id: "salad",    label: "Салат" },
  { id: "steak",    label: "Стейк" },
  { id: "chicken",  label: "Курица" },
  { id: "toast",    label: "Тосты" },
  { id: "roast",    label: "Вырезка" },
  { id: "shashlik", label: "Шашлык" },
  { id: "pot",      label: "Кастрюля" },
  { id: "bread",    label: "Хлеб" },
] as const;

export type FoodKind = typeof FOOD_KINDS[number]["id"];

function pickPaletteByTitle(title: string) {
  let x = 0;
  for (let i = 0; i < title.length; i++) x = (x * 31 + title.charCodeAt(i)) >>> 0;
  const keys = Object.keys(FOOD_COLORS) as FoodColor[];
  return FOOD_COLORS[keys[x % keys.length]];
}

interface Props {
  title?: string;
  kind?: string | null;
  color?: string | null;
  className?: string;
}

export function FoodGlyph({ title = "", kind, color, className }: Readonly<Props>) {
  const resolvedKind = (kind || "soup") as FoodKind;
  const pal = color && color in FOOD_COLORS
    ? FOOD_COLORS[color as FoodColor]
    : pickPaletteByTitle(title);
  const { bg, fg, dk } = pal;

  return (
    <div
      className={className}
      style={{
        width: "100%",
        aspectRatio: "4 / 3",
        background: bg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <svg viewBox="0 0 120 90" width="72%" height="72%" style={{ maxWidth: 180 }}>
        {resolvedKind === "soup" && (
          <g>
            <ellipse cx="60" cy="62" rx="40" ry="6" fill={fg} opacity=".22" />
            <path d="M22 50 Q60 84 98 50 Z" fill={fg} />
            <ellipse cx="60" cy="50" rx="38" ry="9" fill={dk} />
            <circle cx="52" cy="46" r="4" fill={bg} opacity=".6" />
            <circle cx="66" cy="44" r="3" fill={bg} opacity=".5" />
            <path d="M45 36 Q50 28 55 36 M70 32 Q75 24 80 32" stroke={fg} strokeWidth="1.5" fill="none" opacity=".7" strokeLinecap="round" />
          </g>
        )}
        {resolvedKind === "noodles" && (
          <g>
            <ellipse cx="60" cy="62" rx="40" ry="6" fill={fg} opacity=".22" />
            <circle cx="60" cy="50" r="34" fill={fg} />
            <circle cx="60" cy="50" r="30" fill={dk} />
            <path d="M34 50 Q45 42 56 50 M42 55 Q55 45 68 55 M50 48 Q62 40 74 48 M40 45 Q55 52 70 42 M48 58 Q60 50 72 58" stroke={bg} strokeWidth="1.4" fill="none" opacity=".8" strokeLinecap="round" />
            <circle cx="72" cy="44" r="3" fill={bg} />
            <circle cx="48" cy="54" r="2" fill={bg} />
          </g>
        )}
        {resolvedKind === "eggs" && (
          <g>
            <ellipse cx="60" cy="62" rx="42" ry="6" fill={fg} opacity=".22" />
            <path d="M26 54 Q20 42 32 36 Q28 26 42 30 Q48 20 62 28 Q74 22 82 34 Q96 34 96 48 Q100 56 88 60 Q82 68 70 62 Q60 70 48 62 Q36 66 30 58 Z" fill="#FFFBF2" opacity=".95" />
            <circle cx="50" cy="44" r="7" fill={dk} />
            <circle cx="50" cy="44" r="5" fill="#F6C948" />
            <circle cx="72" cy="48" r="6" fill={dk} />
            <circle cx="72" cy="48" r="4" fill="#F6C948" />
          </g>
        )}
        {resolvedKind === "pancakes" && (
          <g>
            <ellipse cx="60" cy="65" rx="38" ry="5" fill={fg} opacity=".25" />
            <ellipse cx="60" cy="60" rx="34" ry="5" fill={fg} />
            <ellipse cx="60" cy="54" rx="33" ry="5" fill={dk} />
            <ellipse cx="60" cy="48" rx="31" ry="5" fill={fg} />
            <ellipse cx="60" cy="42" rx="29" ry="5" fill={dk} />
            <path d="M38 40 Q45 34 58 38 Q72 34 82 40 Q76 46 58 43 Q42 45 38 40 Z" fill="#F6C948" opacity=".9" />
            <circle cx="60" cy="38" r="3" fill="#B84C2A" />
          </g>
        )}
        {resolvedKind === "pelmeni" && (
          <g>
            <ellipse cx="60" cy="62" rx="40" ry="6" fill={fg} opacity=".22" />
            <ellipse cx="60" cy="55" rx="42" ry="10" fill={fg} />
            <ellipse cx="60" cy="52" rx="36" ry="7" fill={dk} />
            <g fill="#FFFBF2">
              <path d="M40 48 q4 -8 10 -4 q6 -4 10 4 q-4 6 -10 4 q-6 2 -10 -4z" />
              <path d="M62 50 q4 -8 10 -4 q6 -4 10 4 q-4 6 -10 4 q-6 2 -10 -4z" />
              <path d="M50 40 q4 -8 10 -4 q6 -4 10 4 q-4 6 -10 4 q-6 2 -10 -4z" />
            </g>
            <circle cx="50" cy="47" r="1.2" fill={dk} />
            <circle cx="72" cy="49" r="1.2" fill={dk} />
            <circle cx="61" cy="39" r="1.2" fill={dk} />
          </g>
        )}
        {resolvedKind === "pie" && (
          <g>
            <ellipse cx="60" cy="64" rx="40" ry="5" fill={fg} opacity=".22" />
            <ellipse cx="60" cy="55" rx="40" ry="10" fill={fg} />
            <ellipse cx="60" cy="50" rx="36" ry="8" fill={dk} />
            <ellipse cx="60" cy="48" rx="30" ry="6" fill={fg} />
            <path d="M36 48 L84 48 M40 44 L80 52 M40 52 L80 44" stroke={dk} strokeWidth="1.4" opacity=".7" />
          </g>
        )}
        {resolvedKind === "pizza" && (
          <g>
            <ellipse cx="60" cy="62" rx="40" ry="5" fill={fg} opacity=".22" />
            <circle cx="60" cy="48" r="36" fill={fg} />
            <circle cx="60" cy="48" r="32" fill="#F6C948" opacity=".8" />
            <circle cx="60" cy="48" r="30" fill="#E86B3A" opacity=".75" />
            <circle cx="48" cy="40" r="3" fill="#7A2416" />
            <circle cx="70" cy="38" r="3" fill="#7A2416" />
            <circle cx="56" cy="54" r="3" fill="#7A2416" />
            <circle cx="72" cy="56" r="3" fill="#7A2416" />
            <circle cx="42" cy="52" r="2" fill="#FFFBF2" />
            <circle cx="64" cy="46" r="2" fill="#FFFBF2" />
          </g>
        )}
        {resolvedKind === "salad" && (
          <g>
            <ellipse cx="60" cy="62" rx="40" ry="5" fill={fg} opacity=".22" />
            <ellipse cx="60" cy="52" rx="42" ry="10" fill={fg} />
            <ellipse cx="60" cy="48" rx="38" ry="8" fill={dk} />
            <path d="M32 46 Q38 36 48 40 Q52 50 40 52 Q34 52 32 46Z" fill="#6B7A4B" />
            <path d="M60 38 Q68 32 76 40 Q76 50 64 50 Q58 46 60 38Z" fill="#8A9B5C" />
            <path d="M80 44 Q88 44 88 52 Q82 56 74 52 Q72 46 80 44Z" fill="#6B7A4B" />
            <circle cx="50" cy="50" r="3" fill="#B84C2A" />
            <circle cx="68" cy="52" r="3" fill="#B84C2A" />
          </g>
        )}
        {resolvedKind === "steak" && (
          <g>
            <ellipse cx="60" cy="64" rx="40" ry="5" fill={fg} opacity=".22" />
            <ellipse cx="60" cy="54" rx="42" ry="9" fill={fg} />
            <ellipse cx="60" cy="51" rx="38" ry="7" fill={dk} />
            <path d="M34 48 Q42 36 58 38 Q76 34 84 44 Q88 54 72 56 Q54 58 42 54 Q32 52 34 48Z" fill="#7A2416" />
            <path d="M42 46 Q55 42 70 44 M46 50 Q60 48 74 50" stroke="#3A110A" strokeWidth="1.2" fill="none" opacity=".8" />
            <path d="M62 38 L64 34 M70 40 L72 36" stroke={fg} strokeWidth="1.4" opacity=".5" strokeLinecap="round" />
          </g>
        )}
        {resolvedKind === "chicken" && (
          <g>
            <ellipse cx="60" cy="64" rx="36" ry="4" fill={fg} opacity=".22" />
            <path d="M38 42 Q34 30 46 28 Q58 28 58 40 L74 56 Q78 64 70 68 Q60 72 56 64 L40 48 Q36 46 38 42Z" fill="#B8863A" />
            <path d="M38 42 Q34 30 46 28 Q58 28 58 40 L56 42 Q50 34 44 36 Q38 38 38 42Z" fill="#FFFBF2" opacity=".85" />
            <circle cx="44" cy="36" r="1.2" fill="#7A4E12" />
            <circle cx="50" cy="34" r="1.2" fill="#7A4E12" />
            <path d="M66 60 Q70 58 72 62" stroke="#7A4E12" strokeWidth="1.2" fill="none" />
          </g>
        )}
        {resolvedKind === "toast" && (
          <g>
            <ellipse cx="60" cy="68" rx="34" ry="4" fill={fg} opacity=".22" />
            <path d="M36 34 Q36 24 46 22 Q56 18 68 22 Q80 22 84 32 L84 58 Q84 64 78 64 L42 64 Q36 64 36 58 Z" fill="#E8B060" />
            <path d="M40 36 Q40 28 48 26 Q58 22 68 26 Q78 26 80 34 L80 56 Q80 60 76 60 L44 60 Q40 60 40 56 Z" fill="#F6D088" />
            <rect x="52" y="32" width="16" height="10" rx="2" fill="#F6E9B8" />
            <path d="M52 36 L68 36" stroke="#B89028" strokeWidth="1" opacity=".5" />
          </g>
        )}
        {resolvedKind === "roast" && (
          <g>
            <ellipse cx="60" cy="66" rx="40" ry="4" fill={fg} opacity=".22" />
            <ellipse cx="60" cy="56" rx="42" ry="9" fill={fg} />
            <ellipse cx="60" cy="53" rx="38" ry="7" fill={dk} />
            <path d="M30 50 Q34 36 52 34 Q70 30 86 40 Q92 52 78 56 Q62 60 46 56 Q30 54 30 50Z" fill="#8C3A20" />
            <circle cx="30" cy="48" r="4" fill="#F6E9B8" />
            <circle cx="28" cy="50" r="3" fill="#F6E9B8" />
            <path d="M48 44 Q60 42 72 46" stroke="#3A110A" strokeWidth="1.2" fill="none" opacity=".6" />
          </g>
        )}
        {resolvedKind === "shashlik" && (
          <g>
            <ellipse cx="60" cy="70" rx="42" ry="4" fill={fg} opacity=".22" />
            <line x1="14" y1="40" x2="106" y2="40" stroke={fg} strokeWidth="1.6" />
            <rect x="28" y="34" width="10" height="12" rx="2" fill="#8C3A20" />
            <rect x="42" y="34" width="10" height="12" rx="2" fill="#B8863A" />
            <rect x="56" y="34" width="10" height="12" rx="2" fill="#8C3A20" />
            <rect x="70" y="34" width="10" height="12" rx="2" fill="#B8863A" />
            <rect x="84" y="34" width="10" height="12" rx="2" fill="#8C3A20" />
            <line x1="14" y1="58" x2="106" y2="58" stroke={fg} strokeWidth="1.6" />
            <rect x="28" y="52" width="10" height="12" rx="2" fill="#B8863A" />
            <rect x="42" y="52" width="10" height="12" rx="2" fill="#8C3A20" />
            <rect x="56" y="52" width="10" height="12" rx="2" fill="#B8863A" />
            <rect x="70" y="52" width="10" height="12" rx="2" fill="#8C3A20" />
            <rect x="84" y="52" width="10" height="12" rx="2" fill="#B8863A" />
          </g>
        )}
        {resolvedKind === "pot" && (
          <g>
            <rect x="28" y="40" width="64" height="32" rx="4" fill={fg} />
            <rect x="22" y="36" width="76" height="6" rx="3" fill={dk} />
            <path d="M20 38 L14 38 M100 38 L106 38" stroke={dk} strokeWidth="3" strokeLinecap="round" />
            <path d="M45 26 Q48 18 45 12 M55 22 Q58 14 55 8 M65 26 Q68 18 65 12" stroke={fg} strokeWidth="1.5" fill="none" opacity=".5" strokeLinecap="round" />
          </g>
        )}
        {resolvedKind === "bread" && (
          <g>
            <ellipse cx="60" cy="66" rx="42" ry="5" fill={fg} opacity=".22" />
            <path d="M25 58 Q30 30 60 30 Q90 30 95 58 Z" fill={fg} />
            <path d="M38 40 L42 55 M50 35 L52 55 M62 33 L62 55 M74 35 L72 55 M84 40 L80 55" stroke={dk} strokeWidth="1.4" opacity=".6" strokeLinecap="round" />
          </g>
        )}
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          background: "radial-gradient(circle at 30% 30%, rgba(255,255,255,.22), transparent 60%)",
        }}
      />
    </div>
  );
}
