"use client";
import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { БУКВЫ, КАТ_ИМЯ } from "@/lib/категории";

type ТГ = { BackButton?: { show: () => void; hide: () => void; onClick: (f: () => void) => void; offClick: (f: () => void) => void } };

/* Область: все её статьи, у каждой цветные метки категорий, которые в ней бывают. */
export default function Area({ имя, строки }: { имя: string; строки: { ид: string; название: string; кат: string[] }[] }) {
  const роутер = useRouter();
  const назад = () => (window.history.length > 1 ? роутер.back() : роутер.push("/"));
  useEffect(() => {
    const кн = (window as unknown as { Telegram?: { WebApp?: ТГ } }).Telegram?.WebApp?.BackButton;
    if (!кн) return;
    кн.show(); кн.onClick(назад);
    return () => { кн.offClick(назад); кн.hide(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div className="app">
      <header className="artbar">
        <button className="back" onClick={назад} aria-label="Назад">‹ Назад</button>
        <span>Область</span>
        <i />
      </header>
      <div className="scroll art">
        <h1 className="art-title">{имя}</h1>
        <details className="legend">
          <summary>Что значат буквы А–Д</summary>
          <ul>{БУКВЫ.map((б) => <li key={б}><b className={`k k-${б}`}>{б}</b><span>{КАТ_ИМЯ[б]}</span></li>)}</ul>
          <p>Буква показывает, на что указывает статья для призывника, если врач подтвердит диагноз. Решает только комиссия.</p>
        </details>
        <p className="label" style={{ margin: "16px 0 4px" }}>Статьи · {строки.length}</p>
        {строки.map((с) => (
          <Link key={с.ид} href={`/a/${с.ид}`} className="row area-row">
            <b>ст. {с.ид}</b>
            <span>{с.название.length > 120 ? с.название.slice(0, 119).trim() + "…" : с.название}</span>
            <em className="dots">{с.кат.map((к) => <i key={к} className={`k k-${к}`} title={КАТ_ИМЯ[к]}>{к}</i>)}</em>
          </Link>
        ))}
      </div>
    </div>
  );
}
