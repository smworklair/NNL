import { notFound } from "next/navigation";
import статьи from "@/data/статьи.json";
import карточки from "@/data/карточки.json";
import type { Карточка, Статья } from "@/lib/карточка";
import СтатьяЭкран from "@/components/Article";

const все = статьи as unknown as Record<string, Статья>;
const карты = карточки as unknown as Record<string, Карточка>;

export function generateStaticParams() {
  return Object.keys(все).map((id) => ({ id }));
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const а = все[id];
  return { title: а ? `Ст. ${id}. ${а.название}` : "Справка по годности" };
}

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const а = все[id];
  if (!а) notFound();
  return <СтатьяЭкран статья={а} карточка={карты[id] ?? null} />;
}
