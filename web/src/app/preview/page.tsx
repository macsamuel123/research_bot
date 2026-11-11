import Link from "next/link";
import { notFound } from "next/navigation";

const SCREENS = [
  { src: "/r/1", label: "Thread" },
  { src: "/r/4", label: "Researching…" },
  { src: "/r/5", label: "409 on send" },
  { src: "/", label: "New research (streams)" },
] as const;

/** Phone-frame preview of the mock UI; 404 unless NEXT_PUBLIC_USE_MOCKS=1. */
export default async function PreviewPage({
  searchParams,
}: {
  searchParams: Promise<{ screen?: string | string[] }>;
}) {
  if (process.env.NEXT_PUBLIC_USE_MOCKS !== "1") notFound();
  const { screen } = await searchParams;
  const current = SCREENS.find((s) => s.src === screen) ?? SCREENS[0];
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-neutral-900 p-6">
      <nav aria-label="Preview screens" className="flex flex-wrap justify-center gap-2">
        {SCREENS.map((s) => (
          <Link
            key={s.src}
            href={`/preview?screen=${encodeURIComponent(s.src)}`}
            aria-current={s.src === current.src ? "page" : undefined}
            className="inline-flex min-h-11 items-center rounded-lg border border-neutral-700 px-3 text-sm text-neutral-200 hover:bg-neutral-800 aria-[current=page]:border-sky-400"
          >
            {s.label}
          </Link>
        ))}
      </nav>
      <div className="overflow-hidden rounded-[2.5rem] border-8 border-neutral-700 shadow-2xl">
        <iframe
          key={current.src}
          title="Research Bot phone preview"
          src={current.src}
          width={390}
          height={844}
          className="block"
        />
      </div>
    </div>
  );
}
