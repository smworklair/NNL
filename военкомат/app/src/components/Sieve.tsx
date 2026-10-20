"use client";
import { useEffect, useRef, useState } from "react";
import Modes from "./Modes";
import { ViewTransition } from "react";
import Link from "next/link";
import { умныйПоиск, type Ответ } from "@/lib/api";
import { всеСтатьи, нижний, type СтатьяСписка } from "@/lib/статьи";
import { читатьДело, синхронизироватьДело, убратьИзДела, type Отметка } from "@/lib/дело";
import { ДОКУМЕНТЫ } from "@/data/документы";

type Вкладка = "статьи" | "документы" | "дело";
const ВКЛАДКИ: [Вкладка, string][] = [["статьи", "Статьи"], ["документы", "Документы"], ["дело", "Дело"]];
const близость = (p: number) => (p >= 0.85 ? "очень близко" : p >= 0.6 ? "близко" : p >= 0.35 ? "возможно" : "слабое совпадение");
const коротко = (с: string, n: number) => (с.length > n ? с.slice(0, n - 1).trim() + "…" : с);

/* Поиск на весь экран: вкладки сверху, поле внизу над клавиатурой. Умный поиск отвечает от Python-ядра. */
export default function Sieve({ начальный, закрыть }: { начальный: string; закрыть: () => void }) {
  const [q, setQ] = useState(начальный);
  const [вкладка, setВкладка] = useState<Вкладка>("статьи");
  const [ответ, setОтвет] = useState<Ответ | null>(null);
  const [ждём, setЖдём] = useState(false);
  const [сбой, setСбой] = useState(false);
  const [статьи, setСтатьи] = useState<СтатьяСписка[] | null>(null);
  const [дело, setДело] = useState<Отметка[]>([]);
  const ввод = useRef<HTMLInputElement>(null);

  useEffect(() => {
    ввод.current?.focus({ preventScroll: true });
    setДело(читатьДело());
    синхронизироватьДело().then(setДело);
  }, []);
  useEffect(() => {
    всеСтатьи().then(setСтатьи).catch(() => setСтатьи([]));
  }, []);

  useEffect(() => {
    const текст = q.trim();
    if (вкладка !== "статьи" || текст.length < 2) { setОтвет(null); setСбой(false); return; }
    const стоп = new AbortController();
    const таймер = setTimeout(() => {
      setЖдём(true); setСбой(false);
      умныйПоиск(текст, стоп.signal)
        .then((о) => { setОтвет(о); setЖдём(false); })
        .catch((е: unknown) => { if ((е as Error).name !== "AbortError") { setСбой(true); setЖдём(false); } });
    }, 350);
    return () => { clearTimeout(таймер); стоп.abort(); };
  }, [q, вкладка]);

  const ф = нижний(q.trim());
  const названия = (статьи ?? []).filter((а) => !ф || нижний(а.название).includes(ф) || а.ид === ф);
  const кандидаты = (ответ?.статьи ?? []).slice(0, 8);
  const документы = ДОКУМЕНТЫ.filter((д) => !ф || нижний(`${д.имя} ${д.лид} ${д.куда} ${д.вид}`).includes(ф));
  const названиеСтатьи = (ид: string) => статьи?.find((а) => а.ид === ид)?.название ?? "статья Расписания";

  return (
    <div className="sieve" role="dialog" aria-label="Поиск">
      <nav className="tabs" aria-label="Раздел">
        {ВКЛАДКИ.map(([к, имя]) => (
          <button key={к} className={`tab ${вкладка === к ? "on" : ""}`} onClick={() => setВкладка(к)}>{имя}</button>
        ))}
      </nav>
      <div className="sieve-body">
        {вкладка === "статьи" && (
          <>
            {ответ?.расшифровано?.length ? (
              <p className="note">Понял: {ответ.расшифровано.map((р) => `«${р.сокращение}» = ${р.значение}`).join(", ")}</p>
            ) : null}
            {ответ?.предложения && ответ.предложения.length > 1 ? (
              <>
                <h2>Разобрал по предложениям</h2>
                {ответ.предложения.map((п, i) => (
                  <p key={i} className="note" style={{ margin: "4px 2px" }}>«{коротко(п.текст, 60)}» → ст. {п.статья}</p>
                ))}
              </>
            ) : null}
            {кандидаты.length ? <h2>Ближе всего по смыслу</h2> : null}
            {кандидаты.map((а) => {
              const p = а.p_показ ?? а.p;
              const пр = Math.max(2, Math.round(p * 100));
              return (
                <Link key={а.ид} href={`/a/${а.ид}`} className="hit">
                  <span className="t"><b>ст. {а.ид}</b><ViewTransition name={`art-${а.ид}`} share="morph" default="none"><span>{коротко(а.название, 110)}</span></ViewTransition></span>
                  <span className="bar"><u style={{ width: `${пр}%` }} /></span>
                  <em>{близость(p)} · {пр} %{а.пункт ? ` · ближе всего пункт «${а.пункт}»` : ""}</em>
                </Link>
              );
            })}
            {ждём && !ответ ? <p className="note">Разбираю предложения…</p> : null}
            {сбой ? <p className="note">Ядро сейчас не отвечает. Показываю поиск по названиям.</p> : null}
            {ответ && !кандидаты.length && !ждём ? <p className="note">По смыслу ничего не нашлось. Опишите подробнее.</p> : null}
            <h2>{ф ? "Совпадения в названиях" : `Все статьи Расписания болезней · ${статьи?.length ?? 88}`}</h2>
            {статьи === null ? <p className="note">Загружаю статьи…</p> : null}
            {статьи && !названия.length ? <p className="note">В названиях такого нет.</p> : null}
            {названия.map((а) => (
              <Link key={а.ид} href={`/a/${а.ид}`} className="row"><b>ст. {а.ид}</b>{кандидаты.some((к) => к.ид === а.ид) ? <span>{коротко(а.название, 110)}</span> : <ViewTransition name={`art-${а.ид}`} share="morph" default="none"><span>{коротко(а.название, 110)}</span></ViewTransition>}</Link>
            ))}
          </>
        )}
        {вкладка === "документы" && (
          <>
            {!документы.length ? <p className="note">Такого бланка нет. Все бланки: очистите поле поиска.</p> : <h2>Бланки · {документы.length}</h2>}
            {документы.map((д) => (
              <Link key={д.н} href={`/b/${д.н}`} className="row">
                <b>{д.вид}</b><span>{д.имя}</span><em>{д.куда}. {д.лид}</em>
              </Link>
            ))}
          </>
        )}
        {вкладка === "дело" &&
          (дело.length === 0 ? (
            <div className="empty">
              <h3>Дело пока пусто</h3>
              <p>Найдите статью и нажмите «Добавить в моё дело». Здесь соберутся ваши отметки, следующий шаг и нужные бланки.</p>
              <button type="button" className="cta" onClick={() => setВкладка("статьи")}>К статьям</button>
            </div>
          ) : (
            <>
              <Link href="/delo" className="cta" style={{ display: "block", textAlign: "center", textDecoration: "none", marginBottom: 6 }}>Открыть моё дело</Link>
              <h2>В деле · {дело.length}</h2>
              {дело.filter((з) => !ф || нижний(названиеСтатьи(з.ид)).includes(ф) || з.ид === ф).map((з) => (
                <div key={з.ид} className="row-wrap">
                  <Link href={`/a/${з.ид}`} className="row">
                    <b>ст. {з.ид}</b><span>{коротко(названиеСтатьи(з.ид), 90)}</span>
                    <em>{з.статус === "врач" ? "от врача" : "со слов"}</em>
                  </Link>
                  <button type="button" className="rm" aria-label="Убрать из дела" onClick={() => setДело(убратьИзДела(з.ид))}>✕</button>
                </div>
              ))}
            </>
          ))}
      </div>
      <form className="sieve-bar" onSubmit={(е) => е.preventDefault()}>
        <input ref={ввод} value={q} onChange={(е) => setQ(е.target.value)} enterKeyHint="search"
          placeholder="Найти статью: опишите, что беспокоит" autoComplete="off" spellCheck={false} aria-label="Поиск" />
        <button type="button" onClick={закрыть}>Отмена</button>
      </form>
      <div className="dock-modes"><Modes активный="home" /></div>
    </div>
  );
}
