"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Modes from "./Modes";
import type { БлокЧеклист, Карточка, Статья } from "@/lib/карточка";
import { добавитьВДело, естьВДеле, изменитьОтметку, читатьДело } from "@/lib/дело";

type ТГ = { BackButton?: { show: () => void; hide: () => void; onClick: (f: () => void) => void; offClick: (f: () => void) => void } };
type Отмечено = Record<number, Record<number, boolean>>;
const ключ = (ид: string) => `справка_карточка_${ид}`;

/* Расследование, шаг 2: кто подтвердил диагноз, какие документы на руках, чего не хватает и какой бланк подать. */
export default function Case({ статья, карточка }: { статья: Статья; карточка: Карточка | null }) {
  const роутер = useRouter();
  const [врач, setВрач] = useState<boolean | null>(null);
  const [чек, setЧек] = useState<Отмечено>({});
  const назадРеф = useRef(() => {});
  назадРеф.current = () => (window.history.length > 1 ? роутер.back() : роутер.push("/investigate"));

  const блоки = (карточка?.блоки ?? []).map((б, i) => ({ б, i })).filter((х): х is { б: БлокЧеклист; i: number } => х.б.вид === "чеклист");

  useEffect(() => {
    try { const с = JSON.parse(localStorage.getItem(ключ(статья.ид)) || "null"); if (с?.чек) setЧек(с.чек); } catch { /* пусто */ }
    const о = читатьДело().find((з) => з.ид === статья.ид);
    setВрач(о ? о.статус === "врач" : null);
    const кн = (window as unknown as { Telegram?: { WebApp?: ТГ } }).Telegram?.WebApp?.BackButton;
    if (!кн) return;
    const f = () => назадРеф.current();
    кн.show(); кн.onClick(f);
    return () => { кн.offClick(f); кн.hide(); };
  }, [статья.ид]);

  const отметить = (i: number, j: number) => {
    const новое: Отмечено = { ...чек, [i]: { ...(чек[i] ?? {}), [j]: !(чек[i]?.[j]) } };
    setЧек(новое);
    try {
      const с = JSON.parse(localStorage.getItem(ключ(статья.ид)) || "{}");
      localStorage.setItem(ключ(статья.ид), JSON.stringify({ ...с, чек: новое }));
    } catch { /* не сохранится */ }
  };
  const кто = (в: boolean) => {
    setВрач(в);
    if (!естьВДеле(статья.ид)) добавитьВДело(статья.ид, в ? "врач" : "слово");
    else изменитьОтметку(статья.ид, { статус: в ? "врач" : "слово" });
  };

  const всего = блоки.reduce((н, { б }) => н + б.пункты.length, 0);
  const есть = блоки.reduce((н, { б, i }) => н + б.пункты.filter((_, j) => чек[i]?.[j]).length, 0);
  const нехватает = блоки.flatMap(({ б, i }) => б.пункты.filter((_, j) => !чек[i]?.[j]).map((п) => п.текст));
  const полный = всего > 0 && есть === всего;

  let вывод: { заг: string; текст: string; бланки: { н: number; имя: string }[] };
  if (врач === null) {
    вывод = { заг: "Сначала отметьте, кто подтвердил диагноз", текст: "Без этого вывод не построить.", бланки: [] };
  } else if (!врач) {
    вывод = {
      заг: "Пока это только ваши слова",
      текст: "Свои слова и домашние измерения подтверждением не считаются: категорию без заключения врача не называют. Нужно направление на обследование и заключение врача.",
      бланки: [{ н: 1, имя: "Заявление о направлении на дополнительное обследование" }],
    };
  } else if (!всего) {
    вывод = { заг: "Диагноз подтверждён врачом", текст: "Для этой статьи списка документов в справочнике нет. Возьмите к комиссии заключение и выписки, которые у вас есть.", бланки: [{ н: 3, имя: "Заявление о выдаче медицинских документов" }] };
  } else if (!полный) {
    вывод = {
      заг: `Комплект неполный: не хватает ${всего - есть} из ${всего}`,
      текст: "Без этих документов комиссия может не принять решение по вашему случаю. Запросите их в поликлинике.",
      бланки: [{ н: 3, имя: "Заявление о выдаче медицинских документов" }],
    };
  } else {
    вывод = {
      заг: "Комплект собран по тексту статьи",
      текст: "Все документы из списка отмечены. Возьмите их на комиссию. Если решение не устроит, его можно оспорить.",
      бланки: [{ н: 0, имя: "Заявление о выдаче копии решения призывной комиссии" }, { н: 5, имя: "Жалоба в призывную комиссию субъекта" }],
    };
  }

  return (
    <div className="app">
      <header className="artbar">
        <button className="back" onClick={() => назадРеф.current()} aria-label="Назад">‹ Назад</button>
        <span>Расследование · ст. {статья.ид}</span>
        <i />
      </header>
      <div className="scroll art">
        <h1 className="art-title">{статья.название}</h1>

        <p className="label" style={{ margin: "14px 0 8px" }}>1 · Кто подтвердил диагноз</p>
        <div className="seg2" role="group">
          <button type="button" className={врач === false ? "on" : ""} aria-pressed={врач === false} onClick={() => кто(false)}>Только мои слова</button>
          <button type="button" className={врач === true ? "on" : ""} aria-pressed={врач === true} onClick={() => кто(true)}>Подтвердил врач</button>
        </div>

        <p className="label" style={{ margin: "18px 0 8px" }}>2 · Какие документы на руках</p>
        {блоки.length ? блоки.map(({ б, i }) => (
          <div className="cblock" key={i}>
            <h4>{б.заг}</h4>
            {б.пояснение ? <p className="cnote">{б.пояснение}</p> : null}
            {б.пункты.map((п, j) => (
              <div key={j} className={`crow ${чек[i]?.[j] ? "on" : ""}`}>
                <button className="ccheck" role="checkbox" aria-checked={!!чек[i]?.[j]} onClick={() => отметить(i, j)}>
                  <i aria-hidden>{чек[i]?.[j] ? "✓" : ""}</i><span>{п.текст}</span>
                </button>
              </div>
            ))}
          </div>
        )) : <p className="cnote">Для этой статьи в справочнике нет списка документов. Откройте статью и посмотрите её текст.</p>}
        {всего ? <div className="cprog"><div className="cbar"><u style={{ width: `${Math.round((100 * есть) / всего)}%` }} /></div><span>На руках {есть} из {всего}</span></div> : null}

        <p className="label" style={{ margin: "18px 0 8px" }}>3 · Вывод</p>
        <section className={`verdict ${полный && врач ? "ok" : ""}`}>
          <b>{вывод.заг}</b>
          <p>{вывод.текст}</p>
          {врач && !полный && нехватает.length ? <ul>{нехватает.map((т, k) => <li key={k}>{т}</li>)}</ul> : null}
          {вывод.бланки.map((б) => <Link key={б.н} href={`/b/${б.н}`} className="q main" style={{ display: "block", textAlign: "center", marginTop: 8 }}>Бланк: {б.имя}</Link>)}
        </section>
        <div className="qbtns" style={{ marginTop: 12 }}>
          <Link href={`/a/${статья.ид}`} className="q">Открыть статью</Link>
          <Link href="/delo" className="q">Моё дело</Link>
        </div>
        <p className="cnote" style={{ marginTop: 14 }}>Список документов составлен по тексту статьи, врач его не проверял. Решение принимает призывная комиссия.</p>
      </div>
      <div className="dock-modes"><Modes активный="invest" /></div>
    </div>
  );
}
