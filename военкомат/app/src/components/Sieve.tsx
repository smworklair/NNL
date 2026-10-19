"use client";
import { useEffect, useRef, useState } from "react";
import { умныйПоиск, type Ответ } from "@/lib/api";

const близость = (p: number) => (p >= 0.85 ? "очень близко" : p >= 0.6 ? "близко" : p >= 0.35 ? "возможно" : "слабое совпадение");

/* Поиск на весь экран: поле внизу над клавиатурой, результаты сверху. Ответ приходит от Python-ядра. */
export default function Sieve({ начальный, закрыть }: { начальный: string; закрыть: () => void }) {
  const [q, setQ] = useState(начальный);
  const [ответ, setОтвет] = useState<Ответ | null>(null);
  const [ждём, setЖдём] = useState(false);
  const [сбой, setСбой] = useState(false);
  const ввод = useRef<HTMLInputElement>(null);

  useEffect(() => { ввод.current?.focus({ preventScroll: true }); }, []);

  useEffect(() => {
    const текст = q.trim();
    if (текст.length < 2) { setОтвет(null); setСбой(false); return; }
    const стоп = new AbortController();
    const таймер = setTimeout(() => {
      setЖдём(true); setСбой(false);
      умныйПоиск(текст, стоп.signal)
        .then((о) => { setОтвет(о); setЖдём(false); })
        .catch((е: unknown) => { if ((е as Error).name !== "AbortError") { setСбой(true); setЖдём(false); } });
    }, 350);
    return () => { clearTimeout(таймер); стоп.abort(); };
  }, [q]);

  const статьи = (ответ?.статьи ?? []).slice(0, 8);
  return (
    <div className="sieve" role="dialog" aria-label="Поиск">
      <div className="sieve-body">
        {ответ?.расшифровано?.length ? (
          <p className="note">Понял: {ответ.расшифровано.map((р) => `«${р.сокращение}» = ${р.значение}`).join(", ")}</p>
        ) : null}
        {ответ?.предложения && ответ.предложения.length > 1 ? (
          <>
            <h2>Разобрал по предложениям</h2>
            {ответ.предложения.map((п, i) => (
              <p key={i} className="note" style={{ margin: "4px 2px" }}>«{п.текст}» → ст. {п.статья}</p>
            ))}
          </>
        ) : null}
        {статьи.length ? <h2>Ближе всего по смыслу</h2> : null}
        {статьи.map((а) => {
          const p = а.p_показ ?? а.p, пр = Math.max(2, Math.round(p * 100));
          return (
            <button key={а.ид} type="button" className="hit">
              <span className="t"><b>ст. {а.ид}</b><span>{а.название}</span></span>
              <span className="bar"><u style={{ width: `${пр}%` }} /></span>
              <em>{близость(p)} · {пр} %{а.пункт ? ` · ближе всего пункт «${а.пункт}»` : ""}</em>
            </button>
          );
        })}
        {!статьи.length && !ждём && !сбой && q.trim().length < 2 ? (
          <p className="note">Опишите своими словами, что беспокоит: «давление 160 на 100», «минус 7 на оба глаза», «болит колено».</p>
        ) : null}
        {ждём && !ответ ? <p className="note">Разбираю предложения…</p> : null}
        {сбой ? <p className="note">Ядро сейчас не отвечает. Попробуйте ещё раз через минуту.</p> : null}
        {ответ && !статьи.length && !ждём ? <p className="note">Ничего не нашлось. Опишите подробнее.</p> : null}
      </div>
      <form className="sieve-bar" onSubmit={(е) => е.preventDefault()}>
        <input ref={ввод} value={q} onChange={(е) => setQ(е.target.value)} enterKeyHint="search"
          placeholder="Найти статью: опишите, что беспокоит" autoComplete="off" spellCheck={false} aria-label="Поиск" />
        <button type="button" onClick={закрыть}>Отмена</button>
      </form>
    </div>
  );
}
