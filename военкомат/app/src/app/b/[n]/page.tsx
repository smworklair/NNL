import { notFound } from "next/navigation";
import бумаги from "@/data/бумаги.json";
import type { Бумага } from "@/lib/бумаги";
import Paper from "@/components/Paper";

const все = бумаги as unknown as Бумага[];

export function generateStaticParams() {
  return все.map((б) => ({ n: String(б.н) }));
}

export async function generateMetadata({ params }: { params: Promise<{ n: string }> }) {
  const { n } = await params;
  const б = все[Number(n)];
  return { title: б ? `${б.вид}. ${б.имя}` : "Справка по годности" };
}

export default async function Page({ params }: { params: Promise<{ n: string }> }) {
  const { n } = await params;
  const б = все[Number(n)];
  if (!б) notFound();
  return <Paper бумага={б} />;
}
