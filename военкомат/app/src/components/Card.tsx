"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import type { Блок, Карточка, Состояние, Статья } from "@/lib/карточка";
import { категорияПризыва, пустоеСостояние, подходит, тяжесть } from "@/lib/карточка";

const ключХранилища = (ид: string) => `справка_карточка_${ид}`;
const число = (n: number) => String(n).replace(".", ",");

function Цитата({ текст }: { текст: string }) {
  return (
    <details className="quote">
      <summary>В тексте статьи</summary>
      <blockquote>{текст}</blockquote>
    </details>
  );
}

/* Карточка «Проверьте себя»: каждая строка опирается на дословную цитату из текста статьи. */
export default function Card({ статья, карточка }: { статья: Статья; карточка: Карточка }) {
  const [с, setС] = useState<Состояние>(пустоеСостояние());

  useEffect(() => {
    try {
      const сохр = JSON.parse(localStorage.getItem(ключХранилища(статья.ид)) || "null");
      if (сохр) setС({ ...пустоеСостояние(), ...сохр });
    } catch { /* пустая карточка */ }
  }, [статья.ид]);

  const менять = (f: (было: Состояние) => Состояние) =>
    setС((было) => {
      const новое = f(было);
      try { localStorage.setItem(ключХранилища(статья.ид), JSON.stringify(новое)); } catch { /* не сохранится */ }
      return новое;
    });

  const пунктПоБукве = (б: string | null) => статья.пункты.find((п) => п.буква === б);
  const строкаПункта = (б: string) => {
    const п = пунктПоБукве(б);
    return п ? `пункт «${б}» · категория ${категорияПризыва(п)}` : `пункт «${б}»`;
  };
  const пунктыПоСтатье = статья.пункты;

  const вид = (б: Блок, i: number) => {
    if (б.вид === "чеклист") {
      const отм = с.чек[i] ?? {};
      const есть = б.пункты.filter((_, j) => отм[j]).length;
      return (
        <div className="cblock" key={i}>
          <h4>{б.заг}</h4>
          {б.пояснение ? <p className="cnote">{б.пояснение}</p> : null}
          {б.пункты.map((п, j) => (
            <div key={j} className={`crow ${отм[j] ? "on" : ""}`}>
              <button className="ccheck" role="checkbox" aria-checked={!!отм[j]}
                onClick={() => менять((х) => ({ ...х, чек: { ...х.чек, [i]: { ...(х.чек[i] ?? {}), [j]: !отм[j] } } }))}>
                <i aria-hidden>{отм[j] ? "✓" : ""}</i><span>{п.текст}</span>
              </button>
              <Цитата текст={п.цитата} />
            </div>
          ))}
          <div className="cprog"><div className="cbar"><u style={{ width: `${Math.round((100 * есть) / б.пункты.length)}%` }} /></div><span>На руках {есть} из {б.пункты.length}</span></div>
        </div>
      );
    }
    if (б.вид === "ползунок") {
      const зн: Record<string, number> = {};
      б.поля.forEach((п) => { зн[п.ключ] = с.пол[i]?.[п.ключ] ?? п.знач; });
      const подошли = б.правила.filter((п) => подходит(п, зн)).sort((а, в) => тяжесть(пунктыПоСтатье, а.пункт) - тяжесть(пунктыПоСтатье, в.пункт));
      const лучшее = подошли[0];
      return (
        <div className="cblock" key={i}>
          <h4>{б.заг}</h4>
          {б.пояснение ? <p className="cnote">{б.пояснение}</p> : null}
          {б.поля.map((п) => (
            <div className="cfield" key={п.ключ}>
              <div className="cval"><b>{число(зн[п.ключ])}</b><span>{п.подпись} · {п.ед}</span></div>
              <input type="range" min={п.мин} max={п.макс} step={п.шаг} value={зн[п.ключ]} aria-label={п.подпись}
                onChange={(е) => { const v = Number(е.target.value); менять((х) => ({ ...х, пол: { ...х.пол, [i]: { ...(х.пол[i] ?? {}), [п.ключ]: v } } })); }} />
            </div>
          ))}
          <div className={`cresult ${лучшее ? "yes" : ""}`}>
            {лучшее ? (
              <>
                <b>По этим числам: {строкаПункта(лучшее.пункт)}</b>
                <span>{лучшее.текст}</span>
                <Цитата текст={лучшее.цитата} />
                <button className="clink" onClick={() => document.getElementById(`step-${лучшее.пункт}`)?.scrollIntoView({ behavior: "smooth", block: "center" })}>Показать ступень в статье</button>
              </>
            ) : (
              <>
                <b>Ниже порогов этой статьи</b>
                <span>По этим числам ни один пункт не называется. Решает врач.</span>
              </>
            )}
          </div>
        </div>
      );
    }
    if (б.вид === "признаки") {
      const отм = с.приз[i] ?? {};
      const выбр = б.варианты.filter((_, j) => отм[j]);
      const буквы = выбр.map((в) => в.пункт).filter((х): х is string => !!х);
      const тяжелейший = буквы.sort((а, в) => тяжесть(пунктыПоСтатье, а) - тяжесть(пунктыПоСтатье, в))[0];
      return (
        <div className="cblock" key={i}>
          <h4>{б.заг}</h4>
          {б.пояснение ? <p className="cnote">{б.пояснение}</p> : null}
          {б.варианты.map((в, j) => (
            <div key={j} className={`crow ${отм[j] ? "on" : ""}`}>
              <button className="ccheck" role="checkbox" aria-checked={!!отм[j]}
                onClick={() => менять((х) => ({ ...х, приз: { ...х.приз, [i]: { ...(х.приз[i] ?? {}), [j]: !отм[j] } } }))}>
                <i aria-hidden>{отм[j] ? "✓" : ""}</i>
                <span>{в.текст}{в.пункт ? <em> пункт «{в.пункт}»</em> : null}</span>
              </button>
              {в.обследование ? <p className="cexam">Чем подтверждается: {в.обследование}</p> : null}
              <Цитата текст={в.цитата} />
            </div>
          ))}
          <div className={`cresult ${выбр.length ? "yes" : ""}`}>
            {выбр.length ? (
              <>
                <b>Выбрано признаков: {выбр.length}{тяжелейший ? `. Тяжелее всего указывает на ${строкаПункта(тяжелейший)}` : ""}</b>
                <span>Это то, что указывает на пункт, а не вывод: нужен документ врача.</span>
              </>
            ) : (
              <>
                <b>Ничего не выбрано</b>
                <span>Отметьте то, что у вас подтверждено документами.</span>
              </>
            )}
          </div>
        </div>
      );
    }
    const да = !!с.искл[i];
    return (
      <div className="cblock cexc" key={i}>
        <h4>{б.заг}</h4>
        <p className="cnote">{б.текст}</p>
        <Цитата текст={б.цитата} />
        <div className="cbtns">
          <button className={да ? "on" : ""} onClick={() => менять((х) => ({ ...х, искл: { ...х.искл, [i]: true } }))}>Да, это про меня</button>
          <button className={!да ? "on" : ""} onClick={() => менять((х) => ({ ...х, искл: { ...х.искл, [i]: false } }))}>Нет</button>
        </div>
        {да ? (
          <div className="cresult yes">
            <b>Тогда смотрите статью {б.статья}</b>
            <span>Для этого случая освидетельствование проводится по другой статье.</span>
            <Link className="clink" href={`/a/${б.статья}`}>Открыть ст. {б.статья}</Link>
          </div>
        ) : null}
      </div>
    );
  };

  /* сводка: чего не хватает по спискам документов */
  const сводка = карточка.блоки
    .map((б, i) => (б.вид === "чеклист" ? { заг: б.заг, нет: б.пункты.filter((_, j) => !(с.чек[i] ?? {})[j]), всего: б.пункты.length } : null))
    .filter(Boolean) as { заг: string; нет: { текст: string }[]; всего: number }[];

  return (
    <section className="card3">
      <div className="chead">
        <h3>Проверьте себя</h3>
        <span className={`cbadge ${карточка.статус === "проверено" ? "ok" : ""}`}>{карточка.статус === "проверено" ? "проверено" : "черновик"}</span>
      </div>
      {карточка.статус !== "проверено" ? <p className="cnote">Составлено по тексту статьи, врач не проверял. У каждой строки есть цитата из статьи.</p> : null}
      {карточка.блоки.map(вид)}
      {сводка.length ? (
        <div className="csum">
          <b>Итог по вашим отметкам</b>
          <ul>
            {сводка.map((с2, i) =>
              с2.нет.length ? (
                <li key={i}>Не хватает документов ({с2.нет.length} из {с2.всего}): {с2.нет.map((н) => н.текст).join("; ")}.</li>
              ) : (
                <li key={i} className="ok">Документы из списка «{с2.заг}» у вас на руках.</li>
              ),
            )}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
