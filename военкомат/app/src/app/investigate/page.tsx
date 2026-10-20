import статьи from "@/data/статьи.json";
import type { Статья } from "@/lib/карточка";
import Investigate from "@/components/Investigate";

export const metadata = { title: "Расследование" };

export default function Page() {
  const названия = Object.fromEntries(Object.entries(статьи as unknown as Record<string, Статья>).map(([id, а]) => [id, а.название]));
  return <Investigate названия={названия} />;
}
