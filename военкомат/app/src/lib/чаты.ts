/* История чатов помощника: только на этом устройстве, последние 12. */
import type { ОтветХода } from "./помощник";

export type Сообщение = { кто: "я" | "ядро"; текст: string; ответ?: ОтветХода; ошибка?: boolean; повтор?: string };
export type Чат = { ид: string; в: number; сообщения: Сообщение[] };

const КЛЮЧ = "справка_помощник_чаты";

export function читатьЧаты(): Чат[] {
  try { const с = JSON.parse(localStorage.getItem(КЛЮЧ) || "[]"); return Array.isArray(с) ? с : []; } catch { return []; }
}
function писать(с: Чат[]) { try { localStorage.setItem(КЛЮЧ, JSON.stringify(с.slice(0, 12))); } catch { /* не сохранится */ } }

export function сохранитьЧат(ид: string, сообщения: Сообщение[]) {
  if (!сообщения.length) return;
  const без = читатьЧаты().filter((ч) => ч.ид !== ид);
  писать([{ ид, в: Date.now(), сообщения: сообщения.slice(-60) }, ...без]);
}
export function удалитьЧат(ид: string) { писать(читатьЧаты().filter((ч) => ч.ид !== ид)); }
export function очиститьЧаты() { писать([]); }

export const заглавиеЧата = (ч: Чат) => {
  const о = ч.сообщения.find((м) => м.кто === "ядро" && м.ответ?.рейтинг?.[0] && Number(м.ответ.рейтинг[0].p) >= 0.05)?.ответ?.рейтинг?.[0];
  if (о) return `ст. ${о.статья} · ${о.название}`.slice(0, 60);
  return (ч.сообщения.find((м) => м.кто === "я")?.текст ?? "Разговор").slice(0, 60);
};
