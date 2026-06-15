import { useState } from "react";
import { FoodGlyph } from "@/components/FoodGlyph";

const API_URL = import.meta.env.VITE_API_URL || "https://api.telnor.ru";

interface Props {
  title?: string;
  kind?: string | null;
  color?: string | null;
  imageUrl?: string | null;
  className?: string;
}

export function RecipeImage({ title = "", kind, color, imageUrl, className }: Readonly<Props>) {
  const [failed, setFailed] = useState(false);

  if (imageUrl && !failed) {
    const src = imageUrl.startsWith("http") ? imageUrl : `${API_URL}${imageUrl}`;
    return (
      <div
        className={className}
        style={{ width: "100%", aspectRatio: "4 / 3", overflow: "hidden" }}
      >
        <img
          src={src}
          alt={title}
          loading="lazy"
          onError={() => setFailed(true)}
          style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
        />
      </div>
    );
  }

  return <FoodGlyph title={title} kind={kind} color={color} className={className} />;
}
