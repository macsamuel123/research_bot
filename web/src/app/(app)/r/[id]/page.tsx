import { notFound } from "next/navigation";

import { Thread } from "@/components/Thread";

export default async function ThreadPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  return <Thread key={id} researchId={Number(id)} />;
}
