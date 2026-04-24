interface User {
  id: string;
  first_name?: string | null;
  username: string;
}

const PALETTE = [
  "#B8442A", "#6B7A4B", "#C48A2A", "#7A5AA0",
  "#3F7268", "#3F5E86", "#A8495F", "#7A5A32",
];

function colorForId(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  return PALETTE[hash % PALETTE.length];
}

function initialOf(user: User): string {
  const source = user.first_name?.trim() || user.username;
  return source ? source[0].toUpperCase() : "?";
}

interface AvatarProps {
  user: User;
  size?: number;
  ring?: boolean;
}

export function Avatar({ user, size = 28, ring = false }: Readonly<AvatarProps>) {
  const color = colorForId(user.id);
  return (
    <div
      title={user.first_name || user.username}
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        background: color,
        color: "#FFFBF2",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        fontWeight: 600,
        fontSize: size * 0.42,
        letterSpacing: "0.02em",
        boxShadow: ring ? `0 0 0 2px var(--background), 0 0 0 3px ${color}` : "none",
        flexShrink: 0,
      }}
    >
      {initialOf(user)}
    </div>
  );
}

interface AvatarStackProps {
  users: User[];
  size?: number;
  max?: number;
}

export function AvatarStack({ users, size = 22, max = 4 }: Readonly<AvatarStackProps>) {
  const shown = users.slice(0, max);
  const rest = users.length - shown.length;
  const overlap = Math.round(size * 0.32);

  return (
    <div className="inline-flex items-center">
      {shown.map((user, i) => (
        <div key={user.id} style={{ marginLeft: i === 0 ? 0 : -overlap }}>
          <Avatar user={user} size={size} ring />
        </div>
      ))}
      {rest > 0 && (
        <div
          style={{
            marginLeft: -overlap,
            width: size,
            height: size,
            borderRadius: "50%",
            background: "var(--muted)",
            color: "var(--muted-foreground)",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: size * 0.4,
            fontWeight: 600,
            boxShadow: "0 0 0 2px var(--background)",
          }}
        >
          +{rest}
        </div>
      )}
    </div>
  );
}
