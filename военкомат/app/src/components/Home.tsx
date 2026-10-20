"use client";
import { useState } from "react";
import Sieve from "./Sieve";
import Link from "next/link";
import { СВОДКА, ПРОВЕРКИ, ГЛАВЫ } from "@/data/главная";
import законы from "@/data/законы.json";
import арт from "@/data/арт.json";

const ПРИМЕРЫ: Record<string, string> = {
  "34": "зрение минус 5", "68": "плоскостопие", "43": "давление 160 на 100", "66": "болит спина",
  "52": "астма", "40": "плохо слышу", "86": "рост и вес", "13": "лишний вес и диабет",
};

export default function Home() {
  const [поиск, setПоиск] = useState<string | null>(null);
  return (
    <div className="app">
      <div className="topbar">Справка по годности</div>
      <div className="scroll">
        <section className="hero">
          <h1>Найдите свою болезнь <span>и узнайте, что дальше</span></h1>
        </section>
        <p className="label">Частые запросы</p>
        <div className="chips">
          {ПРОВЕРКИ.map(([ид, имя]) => (
            <button key={ид} className="chip" onClick={() => setПоиск(ПРИМЕРЫ[ид] ?? имя)}>{имя}</button>
          ))}
        </div>
        <div className="carousel" aria-label="Сводка">
          {СВОДКА.map((к, i) => (
            <article key={к.заг} style={{ ["--i" as string]: i }} className={`card poster ${к.вид === "помощь" ? "help" : ""} ${к.вид === "донат" ? "donate" : ""} ${к.вид === "важно" ? "important" : ""}`}>
              {к.арт ? <span className={`свод-арт арт-${к.арт}`} aria-hidden="true" dangerouslySetInnerHTML={{ __html: (арт as Record<string, string>)[к.арт] }} /> : null}
              <div className="pbody">
                <div className="ptop"><span className="kind">{к.метка}</span><span className="num">{i + 1}/{СВОДКА.length}</span></div>
                <h3>{к.заг}</h3>
                <p>{к.текст}</p>
                {к.ссылка ? <a href={к.ссылка} target={к.ссылка.startsWith("http") ? "_blank" : undefined} rel="noopener noreferrer">{к.действие}</a> : null}
              </div>
            </article>
          ))}
        </div>
        <section className="areas">
          <div className="head label" style={{ margin: "14px 0 6px" }}><span>Области</span><span>{ГЛАВЫ.length}</span></div>
          {ГЛАВЫ.map((г, i) => (
            <Link key={г.имя} href={`/g/${i}`} className="area">
              <i>{String(i + 1).padStart(2, "0")}</i><b>{г.имя}</b><span>{г.б - г.а + 1}</span>
            </Link>
          ))}
        </section>
        <section className="areas">
          <div className="head label" style={{ margin: "18px 0 6px" }}><span>Права и порядок</span><span>{законы.length}</span></div>
          {законы.map((з) => (
            <Link key={з.н} href={`/l/${з.н}`} className="area law">
              <i>{String(з.н + 1).padStart(2, "0")}</i>
              <b>{з.название}<small>{з.группа} · {з.тикет}</small></b>
            </Link>
          ))}
        </section>
      </div>
      <div className="dock">
        <button className="search" onClick={() => setПоиск("")}>Жалобы своими словами: колет сердце, минус 7…</button>
        <div className="modes" role="group" aria-label="Режим">
          <button className="mode on">Расследование</button>
          <Link href="/helper" className="mode">Помощник<em>α</em></Link>
        </div>
      </div>
      {поиск !== null ? <Sieve начальный={поиск} закрыть={() => setПоиск(null)} /> : null}
    </div>
  );
}
