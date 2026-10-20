"use client";
import { useEffect, useState, ViewTransition } from "react";
import { useRouter } from "next/navigation";
import type { Карточка, Статья } from "@/lib/карточка";
import { категорияПризыва } from "@/lib/карточка";
import { БУКВЫ, КАТ_ИМЯ, КАТ_СМЫСЛ, буква } from "@/lib/категории";
import { добавитьВДело, естьВДеле } from "@/lib/дело";
import CardView from "./Card";
import { Calculator, Myopia, type Подсветка } from "./Calculator";

type ТГ = { BackButton?: { show: () => void; hide: () => void; onClick: (f: () => void) => void; offClick: (f: () => void) => void } };

/* Страница статьи: ступени по буквам, примечания и карточка «Проверьте себя». */
export default function Article({ статья, карточка }: { статья: Статья; карточка: Карточка | null }) {
  const роутер = useRouter();
  const [открытыПримечания, setОткрыто] = useState(false);
  const [вДеле, setВДеле] = useState(false);
  const [свет, setСвет] = useState<Подсветка>({ буквы: [], категория: null });

  const назад = () => (window.history.length > 1 ? роутер.back() : роутер.push("/"));

  useEffect(() => {
    setВДеле(естьВДеле(статья.ид));
    const кн = (window as unknown as { Telegram?: { WebApp?: ТГ } }).Telegram?.WebApp?.BackButton;
    if (!кн) return;
    кн.show(); кн.onClick(назад);
    return () => { кн.offClick(назад); кн.hide(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [статья.ид]);

  return (
    <div className="app">
      <header className="artbar">
        <button className="back" onClick={назад} aria-label="Назад">‹ Назад</button>
        <span>Ст. {статья.ид}</span>
        <i />
      </header>
      <div className="scroll art">
        <ViewTransition name={`art-${статья.ид}`} share="morph" default="none"><h1 className="art-title">{статья.название}</h1></ViewTransition>
        <p className="label" style={{ margin: "14px 0 8px" }}>Ступени · категория для призывника</p>
        <details className="legend">
          <summary>Что значат буквы А–Д</summary>
          <ul>{БУКВЫ.map((б) => <li key={б}><b className={`k k-${б}`}>{б}</b><span>{КАТ_ИМЯ[б]}. {КАТ_СМЫСЛ[б]}</span></li>)}</ul>
          <p>Категория для призывника, если врач подтвердит диагноз. Решает только комиссия.</p>
        </details>
        <div className="steps">
          {статья.пункты.map((п) => (
            <div key={п.буква} id={`step-${п.буква}`} className={`step ${свет.буквы.includes(п.буква) ? "lit" : ""}`}>
              <span className="letter">{п.буква}</span>
              <span className="desc">{п.описание}</span>
              <span className={`cat k-${буква(категорияПризыва(п))}`}>{категорияПризыва(п)}</span>
            </div>
          ))}
          {!статья.пункты.length ? <p className="note">Статья без деления на пункты.</p> : null}
        </div>

        {статья.ид === "34" ? <Myopia при={setСвет} /> : null}
        {["13", "40", "86"].includes(статья.ид) ? <Calculator ид={статья.ид} при={setСвет} /> : null}

        {карточка && карточка.блоки.length ? <CardView статья={статья} карточка={карточка} /> : null}

        {статья.примечания.length ? (
          <section className="notes">
            <button className="notes-head" onClick={() => setОткрыто(!открытыПримечания)} aria-expanded={открытыПримечания}>
              <span>Примечания к статье</span><i>{открытыПримечания ? "−" : "+"}</i>
            </button>
            {открытыПримечания ? статья.примечания.map((н, i) => <p key={i}>{н}</p>) : null}
          </section>
        ) : null}
      </div>
      <div className="dock">
        <button className={`add ${вДеле ? "done" : ""}`} onClick={() => { добавитьВДело(статья.ид); setВДеле(true); }}>
          {вДеле ? "В моём деле ✓" : "Добавить в моё дело"}
        </button>
      </div>
    </div>
  );
}
