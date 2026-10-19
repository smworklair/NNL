/* Типы данных статьи и карточки «Проверьте себя» и расчёт по правилам. Данные собирает военкомат/карточки/собрать.py. */
export type Пункт = { буква: string; описание: string; графы: string[] };
export type Статья = { ид: string; название: string; пункты: Пункт[]; примечания: string[] };

export type Условие = { от?: number; до?: number; больше?: number; меньше?: number };
export type Правило = { когда: Record<string, Условие>; режим?: "и" | "или"; пункт: string; текст: string; цитата: string };
export type Поле = { ключ: string; подпись: string; ед: string; мин: number; макс: number; шаг: number; знач: number };

export type БлокЧеклист = { вид: "чеклист"; заг: string; пояснение?: string; пункты: { текст: string; цитата: string }[] };
export type БлокПолзунок = { вид: "ползунок"; заг: string; пояснение?: string; поля: Поле[]; правила: Правило[] };
export type БлокПризнаки = {
  вид: "признаки"; заг: string; пояснение?: string; множественный?: boolean;
  варианты: { текст: string; пункт: string | null; цитата: string; обследование?: string }[];
};
export type БлокИсключение = { вид: "исключение"; заг: string; текст: string; статья: string; цитата: string };
export type Блок = БлокЧеклист | БлокПолзунок | БлокПризнаки | БлокИсключение;
export type Карточка = { ид: string; статус: string; блоки: Блок[] };

/* Состояние карточки на устройстве (тот же ключ и вид, что у старого сайта). */
export type Состояние = {
  чек: Record<number, Record<number, boolean>>;
  пол: Record<number, Record<string, number>>;
  приз: Record<number, Record<number, boolean>>;
  искл: Record<number, boolean>;
};
export const пустоеСостояние = (): Состояние => ({ чек: {}, пол: {}, приз: {}, искл: {} });

/* Чем раньше буква в статье, тем тяжелее ступень: а тяжелее б, б тяжелее в. */
export const тяжесть = (пункты: Пункт[], буква: string | null) => {
  const i = пункты.findIndex((п) => п.буква === буква);
  return i < 0 ? 99 : i;
};

export function подходит(п: Правило, значения: Record<string, number>): boolean {
  const усл = Object.entries(п.когда).map(([ключ, у]) => {
    const v = значения[ключ];
    return v != null && (у.от == null || v >= у.от) && (у.до == null || v <= у.до) && (у.больше == null || v > у.больше) && (у.меньше == null || v < у.меньше);
  });
  if (!усл.length) return false;
  return п.режим === "или" ? усл.some(Boolean) : усл.every(Boolean);
}

export const категорияПризыва = (п: Пункт | undefined) => (п?.графы?.[0] ? п.графы[0].replace(/\s*\(.*$/, "") : "");
