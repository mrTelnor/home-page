interface Props {
  size?: number;
  color?: string;
  stroke?: number;
  className?: string;
}

export function WolfMark({ size = 28, color = "currentColor", stroke = 1.6, className }: Readonly<Props>) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden
      className={className}
    >
      <g
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      >
        <path d="M4 10 L8 4 L11 9 L16 7 L21 9 L24 4 L28 10 L27 20 Q27 26 22 27 L16 28 L10 27 Q5 26 5 20 Z" />
        <path d="M8 6 L9 9" />
        <path d="M24 6 L23 9" />
        <circle cx="12.5" cy="15" r="1" fill={color} stroke="none" />
        <circle cx="19.5" cy="15" r="1" fill={color} stroke="none" />
        <path d="M13 20 L16 22 L19 20" />
        <path d="M16 22 L16 24" />
      </g>
    </svg>
  );
}
