// ---- money (INV-1): integer-only, no division, no floats -------------------------------
// money:start
export function formatCents(cents: number): string {
  if (!Number.isInteger(cents)) {
    throw new TypeError(`formatCents expects integer cents, got ${String(cents)}`);
  }
  const negative = cents < 0;
  const digits = String(negative ? -cents : cents).padStart(3, "0");
  const dollars = digits.slice(0, -2);
  const rest = digits.slice(-2);
  return `${negative ? "-" : ""}$${dollars}.${rest}`;
}
// money:end

// ---- time (not money) -------------------------------------------------------------------
const runTimeFormat = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

/** e.g. "Nov 10, 08:00" in the viewer's local time zone. */
export function formatRunTime(iso: string): string {
  return runTimeFormat.format(new Date(iso));
}

const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;

/** Short relative time for the sidebar: "now", "5m", "3h", "2d", or a date. */
export function formatRelative(iso: string, nowMs: number = Date.now()): string {
  const diff = Math.max(0, nowMs - new Date(iso).getTime());
  if (diff < MINUTE_MS) return "now";
  if (diff < HOUR_MS) return `${Math.floor(diff / MINUTE_MS)}m`;
  if (diff < DAY_MS) return `${Math.floor(diff / HOUR_MS)}h`;
  if (diff < 7 * DAY_MS) return `${Math.floor(diff / DAY_MS)}d`;
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(new Date(iso));
}
