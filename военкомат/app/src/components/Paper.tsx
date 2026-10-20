"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { Бумага } from "@/lib/бумаги";
import {
  плоскийТекст, разобрать, строкиЗаявителя, читатьЗаявителя, читатьЗначения, записатьЗаявителя, записатьЗначения,
  значениеПоля, type Заявитель,
} from "@/lib/бумаги";

type ТГ = { BackButton?: { show: () => void; hide: () => void; onClick: (f: () => void) => void; offClick: (f: () => void) => void } };

/* Бланк: слева заполнение пропусков и своих данных, ниже готовый документ. Печать и PDF делает браузер (печатается только документ). */
export default function Paper({ бумага }: { бумага: Бумага }) {
  const роутер = useRouter();
  const разбор = useMemo(() => разобрать(бумага), [бумага]);
  const [знач, setЗнач] = useState<Record<number, string>>({});
  const [я, setЯ] = useState<Заявитель>({});
  const [скопировано, setСкопировано] = useState(false);
  const [готово, setГотово] = useState(false);

  const назад = () => (window.history.length > 1 ? роутер.back() : роутер.push("/"));
  useEffect(() => {
    setЗнач(читатьЗначения(бумага.н));
    setЯ(читатьЗаявителя());
    setГотово(true);
    const кн = (window as unknown as { Telegram?: { WebApp?: ТГ } }).Telegram?.WebApp?.BackButton;
    if (!кн) return;
    кн.show(); кн.onClick(назад);
    return () => { кн.offClick(назад); кн.hide(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [бумага.н]);

  const поменятьЗнач = (и: number, з: string) => { const н = { ...знач, [и]: з }; setЗнач(н); записатьЗначения(бумага.н, н); };
  const поменятьЯ = (к: keyof Заявитель, з: string) => { const н = { ...я, [к]: з }; setЯ(н); записатьЗаявителя(н); };
  const текст = плоскийТекст(бумага, разбор, знач, я);
  const копировать = async () => {
    try { await navigator.clipboard.writeText(текст); setСкопировано(true); setTimeout(() => setСкопировано(false), 1800); } catch { /* буфер недоступен */ }
  };
  const заполнено = разбор.поля.filter((п) => (знач[п.и] ?? "").trim()).length;

  return (
    <div className="app paper-app">
      <header className="artbar">
        <button className="back" onClick={назад} aria-label="Назад">‹ Назад</button>
        <span>{бумага.вид}</span>
        <i />
      </header>
      <div className="scroll art">
        <h1 className="art-title">{бумага.имя}</h1>
        <p className="cnote">{бумага.лид}</p>

        <section className="calc no-print">
          <h3>Ваши данные</h3>
          <p className="cnote">Попадут в шапку бланка. Хранятся только на этом устройстве.</p>
          {([["фио", "Фамилия, имя, отчество"], ["дата", "Дата рождения"], ["адрес", "Адрес регистрации"], ["тел", "Телефон"]] as [keyof Заявитель, string][]).map(([к, подп]) => (
            <label key={к} className="pfield"><span>{подп}</span>
              <input value={я[к] ?? ""} onChange={(е) => поменятьЯ(к, е.target.value)} autoComplete="off" /></label>
          ))}
        </section>

        {разбор.поля.length ? (
          <section className="calc no-print">
            <h3>Заполните пропуски</h3>
            <p className="cnote">Заполнено {заполнено} из {разбор.поля.length}. Можно оставить пустыми и дописать от руки.</p>
            {разбор.поля.map((п) => (
              <label key={п.и} className="pfield"><span>{п.подпись}</span>
                {п.длинное ? (
                  <textarea rows={3} value={знач[п.и] ?? ""} onChange={(е) => поменятьЗнач(п.и, е.target.value)} />
                ) : (
                  <input type={п.дата ? "date" : "text"} value={знач[п.и] ?? ""} onChange={(е) => поменятьЗнач(п.и, е.target.value)} autoComplete="off" />
                )}
              </label>
            ))}
          </section>
        ) : null}

        <p className="label no-print" style={{ margin: "16px 0 8px" }}>Так будет выглядеть бумага</p>
        <article className="doc" id="doc-print">
          <div className="doc-right">{[...бумага.кому, "", ...строкиЗаявителя(готово ? я : {})].join("\n")}</div>
          <p className="doc-title">{бумага.титул}</p>
          {бумага.подтитул ? <p className="doc-sub">{бумага.подтитул}</p> : null}
          {разбор.абзацы.map((сег, i) => (
            <p key={i} className="doc-p">
              {сег.map((с, j) => {
                if ("т" in с) return <span key={j}>{с.т}</span>;
                const з = значениеПоля(с.п, знач[с.п.и]);
                return з ? <mark key={j} className="filled">{з}</mark> : <span key={j}>{с.п.исх}</span>;
              })}
            </p>
          ))}
          <div className="doc-foot">
            <span>«___» ______________ 20___ г.</span>
            <span className="doc-sign">______________ / __________________<br /><small>(подпись) &nbsp;&nbsp;&nbsp;&nbsp;(фамилия, инициалы)</small></span>
          </div>
        </article>
        {бумага.подсказка ? <p className="cnote no-print" style={{ marginTop: 12 }}>{бумага.подсказка}</p> : null}
      </div>
      <div className="dock no-print">
        <div className="pbtns">
          <button className="add" onClick={() => window.print()}>Печать · PDF</button>
          <button className="add ghost" onClick={копировать}>{скопировано ? "Скопировано ✓" : "Копировать текст"}</button>
        </div>
      </div>
    </div>
  );
}
