import статьи from "@/data/статьи.json";
import Delo from "@/components/Delo";

export const metadata = { title: "Моё дело" };

const названия = Object.fromEntries(Object.entries(статьи as unknown as Record<string, { название: string }>).map(([ид, а]) => [ид, а.название]));

export default function Page() {
  return <Delo названия={названия} />;
}
