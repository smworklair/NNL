"use client";
import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Закон } from "@/app/l/[n]/page";

type ТГ = { BackButton?: { show: () => void; hide: () => void; onClick: (f: () => void) => void; offClick: (f: () => void) => void } };

/* Страница закона: о чём он простыми словами, что он даёт человеку и подходящий бланк. */
export default function Law({ закон, бумага }: { закон: Закон; бумага: { н: number; имя: string } | null }) {
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
        <span>{закон.группа}</span>
        <i />
      </header>
      <div className="scroll art">
        <p className="label" style={{ margin: "6px 0" }}>{закон.тикет} · {закон.дата}</p>
        <h1 className="art-title">{закон.название}</h1>
        <p className="cnote">{закон.полное}</p>
        <p className="law-lead">{закон.лид}</p>

        <h2 className="law-h">О чём это</h2>
        {закон.о.map((т, i) => <p key={i} className="law-p">{т}</p>)}
        <h2 className="law-h">Что это даёт вам</h2>
        <ul className="law-ul">{закон.даёт.map((т, i) => <li key={i}>{т}</li>)}</ul>

        {бумага ? (
          <Link href={`/b/${бумага.н}`} className="law-doc">
            <b>Подходящий бланк</b>
            <span>{бумага.имя}</span>
          </Link>
        ) : null}
      </div>
    </div>
  );
}
