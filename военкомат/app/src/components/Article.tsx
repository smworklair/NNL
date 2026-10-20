"use client";
import { useEffect, useState, ViewTransition } from "react";
import Modes from "./Modes";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Карточка, Статья } from "@/lib/карточка";
import { категорияПризыва } from "@/lib/карточка";
import { БУКВЫ, КАТ_ИМЯ, КАТ_СМЫСЛ, буква } from "@/lib/категории";
import { добавитьВДело, естьВДеле, убратьИзДела } from "@/lib/дело";
import CardView from "./Card";
import { Calculator, Myopia, type Подсветка } from "./Calculator";

const ДАЛЬШЕ: Record<string, string> = {
  А: "Годность подтверждается на медосвидетельствовании. Если есть жалобы, принесите документы, которые их подтверждают.",
  Б: "Служба возможна с ограничениями. Покажите комиссии все документы по этому заболеванию.",
  В: "Комиссия решает по документам: принесите выписки и результаты обследований, подтверждающие диагноз.",
  Г: "Решается отсрочка на время лечения. Нужны документы о лечении; потом пройдёте освидетельствование повторно.",
  Д: "Комиссия решает по документам: без выписок и результатов обследований категорию не поставят.",
};

type ТГ = { BackButton?: { show: () => void; hide: () => void; onClick: (f: () => void) => void; offClick: (f: () => void) => void } };

/* Страница статьи: ступени по буквам, примечания и карточка «Проверьте себя». */
export default function Article({ статья, карточка }: { статья: Статья; карточка: Карточка | null }) {
  const роутер = useRouter();
  const [открытыПримечания, setОткрыто] = useState(false);
  const [вДеле, setВДеле] = useState(false);
  const [выбрана, setВыбрана] = useState<string | null>(null);
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

  useEffect(() => {
    if (выбрана) setTimeout(() => document.querySelector(".variant")?.scrollIntoView({ behavior: "smooth", block: "center" }), 80);
  }, [выбрана]);

  const выбранный = статья.пункты.find((п) => п.буква === выбрана);
  const вариант = выбранный ? буква(категорияПризыва(выбранный)) : "";

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
            <button type="button" key={п.буква} id={`step-${п.буква}`} aria-pressed={выбрана === п.буква}
              className={`step ${свет.буквы.includes(п.буква) ? "lit" : ""} ${выбрана === п.буква ? "sel" : ""}`}
              onClick={() => setВыбрана(выбрана === п.буква ? null : п.буква)}>
              <span className="letter">{п.буква}</span>
              <span className="desc">{п.описание}</span>
              <span className={`cat k-${буква(категорияПризыва(п))}`}>{категорияПризыва(п)}</span>
            </button>
          ))}
          {!статья.пункты.length ? <p className="note">Статья без деления на пункты.</p> : null}
        </div>
        {вариант ? (
          <section className="variant" aria-live="polite">
            <div className="variant-head"><span className={`k k-${вариант}`}>{вариант}</span>
              <div><small>Если врач подтвердит</small><b>Категория {вариант}: {КАТ_ИМЯ[вариант].toLowerCase()}</b></div></div>
            <p>{КАТ_СМЫСЛ[вариант]}</p>
            <h4>Что делать дальше</h4>
            <ol>
              <li>{ДАЛЬШЕ[вариант]}</li>
              <li>Если решение комиссии не устраивает, его можно оспорить: <Link href="/b/5">бланк жалобы</Link>.</li>
              <li>Сохраните статью в «моё дело», чтобы не потерять.</li>
            </ol>
            <p className="note">Категорию назначает призывная комиссия по документам врачей. Это справка по тексту Расписания болезней.</p>
          </section>
        ) : null}

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
        <button className={`add ${вДеле ? "done" : ""}`} onClick={() => { if (вДеле) { убратьИзДела(статья.ид); setВДеле(false); } else { добавитьВДело(статья.ид); setВДеле(true); } }}>
          {вДеле ? "В моём деле ✓ · нажмите, чтобы убрать" : "Добавить в моё дело"}
        </button>
        <Modes активный="home" />
      </div>
    </div>
  );
}
