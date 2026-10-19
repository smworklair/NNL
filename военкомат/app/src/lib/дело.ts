/* «Моё дело»: отметки пользователя. Пока хранится на устройстве (тот же ключ и формат, что у старого сайта). */
export type Отметка = { ид: string; статус: "врач" | "слово"; в: number; шагЗакрыт: boolean };

const КЛЮЧ = "справка_годность_дело";

export function читатьДело(): Отметка[] {
  try {
    const с = JSON.parse(localStorage.getItem(КЛЮЧ) || "null");
    if (!Array.isArray(с)) return [];
    return (с as Record<string, unknown>[])
      .filter((з) => з && з.ид)
      .map((з) => ({ ид: String(з.ид), статус: з.статус === "врач" ? "врач" : "слово", в: Number(з.в) || 0, шагЗакрыт: !!з.шагЗакрыт }));
  } catch {
    return [];
  }
}
