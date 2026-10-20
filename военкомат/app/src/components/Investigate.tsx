"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Modes from "./Modes";
import { настройкаПоУмолчанию, ход, type ОтветХода } from "@/lib/помощник";

type ТГ = { BackButton?: { show: () => void; hide: () => void; onClick: (f: () => void) => void; offClick: (f: () => void) => void } };

const ПРИМЕРЫ = [
  { п: "Окулист после капель: −7", т: "Окулист после капель написал: близорукость −7 дптр на оба глаза." },
  { п: "Давление дома 150/95", т: "Давление дома 150 на 95, мерил сам тонометром." },
  { п: "Болит колено после травмы", т: "Болит колено после травмы, был у травматолога." },
];

/* Расследование, шаг 1: словами описать жалобу, ядро находит статью. Дальше проверка комплекта документов (/investigate/[id]). */
export default function Investigate({ названия }: { названия: Record<string, string> }) {
  const роутер = useRouter();
  const [текст, setТекст] = useState("");
  const [ждём, setЖдём] = useState(false);
  const [ответ, setОтвет] = useState<ОтветХода | null>(null);
  const [сбой, setСбой] = useState("");
  const сессия = useRef("i" + Math.random().toString(36).slice(2, 10));
  const назадРеф = useRef(() => {});
  назадРеф.current = () => (window.history.length > 1 ? роутер.back() : роутер.push("/"));

  useEffect(() => {
    const кн = (window as unknown as { Telegram?: { WebApp?: ТГ } }).Telegram?.WebApp?.BackButton;
    if (!кн) return;
    const f = () => назадРеф.current();
    кн.show(); кн.onClick(f);
    return () => { кн.offClick(f); кн.hide(); };
  }, []);

  const искать = async (из?: string) => {
    const т = (из ?? текст).trim();
    if (!т || ждём) return;
    if (из !== undefined) setТекст(из);
    setЖдём(true); setСбой("");
    try { setОтвет(await ход(сессия.current, т, настройкаПоУмолчанию())); }
    catch (е) { setСбой((е as Error).message); setОтвет(null); }
    finally { setЖдём(false); }
  };

  const кандидаты = (ответ?.рейтинг ?? []).filter((р) => Number(р.p) >= 0.03).slice(0, 4);
  const спрашивает = ответ?.действие === "спросить" && !!ответ.вопрос?.текст;

  return (
    <div className="app">
      <header className="artbar">
        <button className="back" onClick={() => назадРеф.current()} aria-label="Назад">‹ Назад</button>
        <span>Расследование</span>
        <i />
      </header>
      <div className="scroll art">
        <h1 className="art-title">Соберите комплект документов</h1>
        <p className="cnote">Опишите, что говорит врач или что вы чувствуете. Ядро найдёт статью Расписания, вы отметите, какие документы уже на руках, и увидите, чего не хватает и какой бланк подать.</p>
        <form className="inv-form" onSubmit={(е) => { е.preventDefault(); искать(); }}>
          <input value={текст} onChange={(е) => setТекст(е.target.value)} placeholder="Например: давление 150 на 95" enterKeyHint="search" aria-label="Жалоба" autoComplete="off" />
          <button type="submit" disabled={ждём || !текст.trim()}>Найти</button>
        </form>
        {!ответ && !ждём ? <div className="chips-wrap" style={{ alignItems: "flex-start", marginTop: 12 }}>{ПРИМЕРЫ.map((п) => <button key={п.п} type="button" className="chip" onClick={() => искать(п.т)}>{п.п}</button>)}</div> : null}
        {ждём ? <p className="cnote" style={{ marginTop: 14 }}>Ищу статью…</p> : null}
        {сбой ? <p className="cnote" style={{ marginTop: 14 }}>Не получилось: {сбой}. <button type="button" className="linkbtn" onClick={() => искать()}>Попробовать ещё раз</button></p> : null}
        {ответ && !ждём ? (
          <section style={{ marginTop: 16 }}>
            <p className="label" style={{ margin: "0 0 6px" }}>{кандидаты.length ? "Похоже на" : "Статья не найдена"}</p>
            {кандидаты.map((р) => (
              <Link key={р.статья} href={`/investigate/${р.статья}`} className="row">
                <b>ст. {р.статья}</b><span>{названия[р.статья] ?? р.название}</span>
                <em>Проверить комплект документов →</em>
              </Link>
            ))}
            {!кандидаты.length ? <p className="cnote">Подходящей статьи не нашлось. Назовите диагноз словами, как его записал врач, или найдите статью в справочнике.</p> : null}
            {спрашивает ? (
              <div style={{ marginTop: 12 }}>
                <p className="cnote">{ответ.вопрос?.текст}</p>
                <div className="qbtns">
                  <button type="button" className="q main" onClick={() => искать("Да")}>Да</button>
                  <button type="button" className="q" onClick={() => искать("Нет")}>Нет</button>
                  <button type="button" className="q" onClick={() => искать("Не знаю")}>Не знаю</button>
                </div>
              </div>
            ) : null}
            <p className="cnote" style={{ marginTop: 14 }}>Это версия ядра по словам, а не диагноз. Категорию называет только врач.</p>
          </section>
        ) : null}
      </div>
      <div className="dock-modes"><Modes активный="invest" /></div>
    </div>
  );
}
