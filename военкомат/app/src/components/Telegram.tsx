"use client";
import { useEffect } from "react";

type ТГ = {
  platform?: string; ready: () => void; expand: () => void; disableVerticalSwipes?: () => void;
  setHeaderColor?: (c: string) => void; setBackgroundColor?: (c: string) => void;
};

/* Внутри настоящего Telegram: раскрыть на весь экран, запретить закрытие свайпом, покрасить шапку. Вне Telegram ничего не делает. */
export default function Telegram() {
  /* Клавиатура: пока поле в фокусе, на <html> стоит класс kb (прячем нижнюю панель режимов); прокрутка пальцем убирает клавиатуру. */
  useEffect(() => {
    const поле = (e: EventTarget | null) => e instanceof HTMLElement && (e.tagName === "INPUT" || e.tagName === "TEXTAREA");
    const вх = (e: FocusEvent) => { if (поле(e.target)) document.documentElement.classList.add("kb"); };
    const вых = () => document.documentElement.classList.remove("kb");
    let y0 = 0;
    const старт = (e: TouchEvent) => { y0 = e.touches[0]?.clientY ?? 0; };
    const сдвиг = (e: TouchEvent) => {
      const а = document.activeElement;
      if (a_ok(а) && Math.abs((e.touches[0]?.clientY ?? 0) - y0) > 14 && !(e.target instanceof Node && (а as HTMLElement).closest("form")?.contains(e.target))) (а as HTMLElement).blur();
    };
    const a_ok = (а: Element | null) => !!а && поле(а);
    document.addEventListener("focusin", вх); document.addEventListener("focusout", вых);
    document.addEventListener("touchstart", старт, { passive: true }); document.addEventListener("touchmove", сдвиг, { passive: true });
    return () => {
      document.removeEventListener("focusin", вх); document.removeEventListener("focusout", вых);
      document.removeEventListener("touchstart", старт); document.removeEventListener("touchmove", сдвиг);
    };
  }, []);

  useEffect(() => {
    const t = (window as unknown as { Telegram?: { WebApp?: ТГ } }).Telegram?.WebApp;
    if (!t || !t.platform || t.platform === "unknown") return;
    try {
      t.ready(); t.expand(); t.disableVerticalSwipes?.();
      const c = getComputedStyle(document.documentElement).getPropertyValue("--bg").trim() || "#121211";
      t.setHeaderColor?.(c); t.setBackgroundColor?.(c);
      document.documentElement.classList.add("in-tg");
    } catch { /* без Telegram работаем как обычная страница */ }
  }, []);
  return null;
}
