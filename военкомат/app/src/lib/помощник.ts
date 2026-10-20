/* Помощник α: разговор с ядром NNL. Режим «только ядро» работает без ключа; со своим ключом включается модель выбранного провайдера.
   Ключ человека хранится только на этом устройстве и уходит на сервер заголовком одного запроса, на сервере он не сохраняется. */
export type Провайдер = { имя: string; модели: string[]; ключ_на_сервере: boolean; документация?: string };
export type Рейтинг = { статья: string; название: string; p: number };
export type Ссылка = { текст: string; статья: string; пункт: string | null; ок: boolean; название?: string };
export type ОтветХода = { ответ: string; рейтинг?: Рейтинг[]; ссылки?: Ссылка[]; закончено?: boolean; действие?: string; ошибка?: string };

export type Настройка = { режим: "nnl" | "свой"; провайдер: string; модель: string; ключ: string };
const КЛЮЧ = "справка_помощник";

export const настройкаПоУмолчанию = (): Настройка => ({ режим: "nnl", провайдер: "", модель: "", ключ: "" });

export function читатьНастройку(): Настройка {
  try { return { ...настройкаПоУмолчанию(), ...JSON.parse(localStorage.getItem(КЛЮЧ) || "{}") }; } catch { return настройкаПоУмолчанию(); }
}
export function записатьНастройку(н: Настройка) {
  try { localStorage.setItem(КЛЮЧ, JSON.stringify(н)); } catch { /* не сохранится */ }
}
export function забытьКлюч() {
  const н = читатьНастройку();
  записатьНастройку({ ...н, режим: "nnl", ключ: "" });
}

const заголовки = (н: Настройка): HeadersInit => {
  const з: Record<string, string> = { "Content-Type": "application/json" };
  if (н.режим === "свой" && н.ключ) { з["X-NNL-Provider"] = н.провайдер; з["X-NNL-Model"] = н.модель; з["X-NNL-Key"] = н.ключ; }
  return з;
};
const путь = (с: string) => `/api/${encodeURIComponent(с)}`;

export async function списокПровайдеров(): Promise<Провайдер[]> {
  const р = await fetch(путь("провайдеры"));
  if (!р.ok) throw new Error(`сервер ответил ${р.status}`);
  return ((await р.json()) as { провайдеры: Провайдер[] }).провайдеры;
}

/* Проверка ключа без расхода токенов: провайдер отдаёт список моделей. */
export async function проверитьКлюч(провайдер: string, ключ: string): Promise<{ ок: boolean; модели?: string[]; ошибка?: string }> {
  const р = await fetch(путь("ключ/проверка"), { method: "POST", headers: { "Content-Type": "application/json", "X-NNL-Provider": провайдер, "X-NNL-Model": "check", "X-NNL-Key": ключ }, body: "{}" });
  return р.json().catch(() => ({ ок: false, ошибка: `сервер ответил ${р.status}` }));
}

export async function ход(сессия: string, текст: string, н: Настройка): Promise<ОтветХода> {
  const режим = н.режим === "nnl" ? "nnl" : "ядро";
  const р = await fetch(путь("turn"), { method: "POST", headers: заголовки(н), body: JSON.stringify({ сессия, режим, текст }) });
  const д = (await р.json().catch(() => ({}))) as ОтветХода;
  if (!р.ok || д.ошибка) throw new Error(д.ошибка || `сервер ответил ${р.status}`);
  return д;
}
