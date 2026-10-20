import { notFound } from "next/navigation";
import статьи from "@/data/статьи.json";
import { ГЛАВЫ } from "@/data/главная";
import Area from "@/components/Area";
import { буква } from "@/lib/категории";

type А = { ид: string; название: string; пункты: { графы?: string[] }[] };
const все = статьи as unknown as Record<string, А>;

export function generateStaticParams() {
  return ГЛАВЫ.map((_, i) => ({ n: String(i) }));
}

export async function generateMetadata({ params }: { params: Promise<{ n: string }> }) {
  const { n } = await params;
  const г = ГЛАВЫ[Number(n)];
  return { title: г ? `${г.имя}. Статьи ${г.а}–${г.б}` : "Справка по годности" };
}

export default async function Page({ params }: { params: Promise<{ n: string }> }) {
  const { n } = await params;
  const г = ГЛАВЫ[Number(n)];
  if (!г) notFound();
  const строки = [];
  for (let и = г.а; и <= г.б; и++) {
    const а = все[String(и)];
    if (!а) continue;
    // какие категории встречаются в статье по графе призывника (первая графа)
    const кат = [...new Set(а.пункты.map((п) => буква(п.графы?.[0])).filter(Boolean))];
    строки.push({ ид: а.ид, название: а.название, кат });
  }
  return <Area имя={г.имя} строки={строки} />;
}
