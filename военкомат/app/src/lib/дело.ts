/* «Моё дело»: отметки пользователя. На устройстве (тот же ключ и формат, что у старого сайта) и, внутри Telegram, на сервере в SQL. */
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

export const естьВДеле = (ид: string) => читатьДело().some((з) => з.ид === ид);

function записатьЛокально(список: Отметка[]) {
  try { localStorage.setItem(КЛЮЧ, JSON.stringify(список)); } catch { /* хранилище недоступно: дело не сохранится на устройстве */ }
}

/* Подпись Telegram: без неё (обычный браузер) сервер ничего не отдаёт, и дело живёт только на устройстве. */
const initData = () => (window as unknown as { Telegram?: { WebApp?: { initData?: string } } }).Telegram?.WebApp?.initData || "";
const заголовки = (): HeadersInit => ({ "Content-Type": "application/json", "X-Telegram-Init-Data": initData() });

export function добавитьВДело(ид: string, статус: "врач" | "слово" = "слово") {
  записатьЛокально([...читатьДело().filter((з) => з.ид !== ид), { ид, статус, в: Date.now(), шагЗакрыт: false }]);
  if (initData()) fetch("/api/delo", { method: "POST", headers: заголовки(), body: JSON.stringify({ ид, статус }) }).catch(() => {});
}

/* Подтягивает дело с сервера и объединяет с локальным: что есть только на устройстве, уходит на сервер. */
export async function синхронизироватьДело(): Promise<Отметка[]> {
  const локально = читатьДело();
  if (!initData()) return локально;
  try {
    const р = await fetch("/api/delo", { headers: заголовки(), cache: "no-store" });
    if (!р.ok) return локально;
    const сервер = (await р.json()) as Отметка[];
    const есть = new Set(сервер.map((з) => з.ид));
    const толькоЗдесь = локально.filter((з) => !есть.has(з.ид));
    await Promise.all(толькоЗдесь.map((з) => fetch("/api/delo", { method: "POST", headers: заголовки(), body: JSON.stringify({ ид: з.ид, статус: з.статус }) }).catch(() => {})));
    const итог = [...сервер, ...толькоЗдесь].sort((а, б) => б.в - а.в);
    записатьЛокально(итог);
    return итог;
  } catch {
    return локально;
  }
}

/* Изменить отметку: статус («со слов» или «от врача») и закрыт ли следующий шаг. На сервер уходит, если вы внутри Telegram. */
export function изменитьОтметку(ид: string, правка: { статус?: "врач" | "слово"; шагЗакрыт?: boolean }): Отметка[] {
  const список = читатьДело().map((з) => (з.ид === ид ? { ...з, ...правка } : з));
  записатьЛокально(список);
  const н = список.find((з) => з.ид === ид);
  if (н && initData()) fetch("/api/delo", { method: "POST", headers: заголовки(), body: JSON.stringify({ ид, статус: н.статус, шагЗакрыт: н.шагЗакрыт }) }).catch(() => {});
  return список;
}

export function убратьИзДела(ид: string): Отметка[] {
  const список = читатьДело().filter((з) => з.ид !== ид);
  записатьЛокально(список);
  if (initData()) fetch(`/api/delo?${new URLSearchParams({ ид })}`, { method: "DELETE", headers: заголовки() }).catch(() => {});
  return список;
}
