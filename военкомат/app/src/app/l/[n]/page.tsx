import { notFound } from "next/navigation";
import законы from "@/data/законы.json";
import бумаги from "@/data/бумаги.json";
import Law from "@/components/Law";

export type Закон = {
  н: number; группа: string; тикет: string; дата: string; бумага: number | null; название: string; лид: string; полное: string; о: string[]; даёт: string[];
};
const все = законы as unknown as Закон[];
const бл = бумаги as unknown as { н: number; имя: string; вид: string }[];

export function generateStaticParams() {
  return все.map((з) => ({ n: String(з.н) }));
}

export async function generateMetadata({ params }: { params: Promise<{ n: string }> }) {
  const { n } = await params;
  const з = все[Number(n)];
  return { title: з ? `${з.группа}: ${з.название}` : "Справка по годности" };
}

export default async function Page({ params }: { params: Promise<{ n: string }> }) {
  const { n } = await params;
  const з = все[Number(n)];
  if (!з) notFound();
  const б = з.бумага != null ? бл.find((х) => х.н === з.бумага) : undefined;
  return <Law закон={з} бумага={б ? { н: б.н, имя: б.имя } : null} />;
}
