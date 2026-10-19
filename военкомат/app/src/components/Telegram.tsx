"use client";
import { useEffect } from "react";

type ТГ = {
  platform?: string; ready: () => void; expand: () => void; disableVerticalSwipes?: () => void;
  setHeaderColor?: (c: string) => void; setBackgroundColor?: (c: string) => void;
};

/* Внутри настоящего Telegram: раскрыть на весь экран, запретить закрытие свайпом, покрасить шапку. Вне Telegram ничего не делает. */
export default function Telegram() {
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
