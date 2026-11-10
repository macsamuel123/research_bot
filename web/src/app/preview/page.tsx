import { notFound } from "next/navigation";

/** Phone-frame preview of the mock UI; 404 unless NEXT_PUBLIC_USE_MOCKS=1. */
export default function PreviewPage() {
  if (process.env.NEXT_PUBLIC_USE_MOCKS !== "1") notFound();
  return (
    <div className="flex min-h-dvh items-center justify-center bg-neutral-900 p-6">
      <div className="overflow-hidden rounded-[2.5rem] border-8 border-neutral-700 shadow-2xl">
        <iframe title="Research Bot phone preview" src="/r/1" width={390} height={844} className="block" />
      </div>
    </div>
  );
}
