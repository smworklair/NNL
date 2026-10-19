/* Список всех 88 статей Расписания болезней: берём у ядра один раз и держим в памяти. */
export type СтатьяСписка = { ид: string; название: string };
let кэш: Promise<СтатьяСписка[]> | null = null;

export function всеСтатьи(): Promise<СтатьяСписка[]> {
  if (!кэш) {
    кэш = fetch(`/api/${encodeURIComponent("статьи")}`)
      .then((р) => { if (!р.ok) throw new Error(String(р.status)); return р.json() as Promise<СтатьяСписка[]>; })
      .then((с) => с.slice().sort((а, б) => parseInt(а.ид, 10) - parseInt(б.ид, 10)))
      .catch((е) => { кэш = null; throw е; });
  }
  return кэш;
}

export const нижний = (с: string) => с.toLowerCase().replace(/ё/g, "е");
