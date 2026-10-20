"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { читатьДело, синхронизироватьДело, изменитьОтметку, убратьИзДела, type Отметка } from "@/lib/дело";

type ТГ = { BackButton?: { show: () => void; hide: () => void; onClick: (f: () => void) => void; offClick: (f: () => void) => void } };
const дата = (мс: number) => {
  if (!мс) return "";
  const д = new Date(мс);
  return `${String(д.getDate()).padStart(2, "0")}.${String(д.getMonth() + 1).padStart(2, "0")}`;
};
const коротко = (с: string, n: number) => (с.length > n ? с.slice(0, n - 1).trim() + "…" : с);

/* «Моё дело»: ваши отметки по статьям, следующий шаг и бланки, которые пригодятся. */
export default function Delo({ названия }: { названия: Record<string, string> }) {
  const роутер = useRouter();
  const [дело, setДело] = useState<Отметка[] | null>(null);
  const назад = () => (window.history.length > 1 ? роутер.back() : роутер.push("/"));

  useEffect(() => {
    setДело(читатьДело());
    синхронизироватьДело().then(setДело);
    const кн = (window as unknown as { Telegram?: { WebApp?: ТГ } }).Telegram?.WebApp?.BackButton;
    if (!кн) return;
    кн.show(); кн.onClick(назад);
    return () => { кн.offClick(назад); кн.hide(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const список = (дело ?? []).slice().sort((а, б) => б.в - а.в);
  const врачей = список.filter((з) => з.статус === "врач").length;
  const кШагу = список.find((з) => !з.шагЗакрыт);

  return (
    <div className="app">
      <header className="artbar">
        <button className="back" onClick={назад} aria-label="Назад">‹ Назад</button>
        <span>Моё дело</span>
        <i />
      </header>
      <div className="scroll art">
        {дело === null ? (
          <p className="note">Загружаю…</p>
        ) : !список.length ? (
          <div className="empty">
            <h3>Дело пока пусто</h3>
            <p>Найдите статью и нажмите «Добавить в моё дело». Здесь соберутся ваши отметки, следующий шаг и нужные бланки.</p>
            <Link href="/" className="cta" style={{ textDecoration: "none", display: "inline-block" }}>К статьям</Link>
          </div>
        ) : (
          <>
            <div className="delo-head">
              <div><b>{список.length}</b><span>{список.length === 1 ? "отметка" : "отметок"} в деле</span></div>
              <div className="delo-chips">
                <span className="chipx">{список.length - врачей} со слов</span>
                <span className="chipx ok">{врачей} от врача</span>
              </div>
            </div>

            {кШагу ? (
              <div className="step-card">
                <span className="label" style={{ margin: 0 }}>Следующий шаг</span>
                <p>
                  {кШагу.статус === "врач"
                    ? `Ст. ${кШагу.ид}: данные уже от врача. Чтобы врачи комиссии их учли, передайте документы в военкомат.`
                    : `Ст. ${кШагу.ид} пока отмечена только с ваших слов. Нужна справка или выписка врача: без неё пункт и категорию определить нельзя.`}
                </p>
                <div className="step-btns">
                  <Link href={`/a/${кШагу.ид}`} className="clink">Открыть статью</Link>
                  <button className="clink" onClick={() => setДело(изменитьОтметку(кШагу.ид, { шагЗакрыт: true }))}>Шаг выполнен</button>
                </div>
              </div>
            ) : (
              <div className="step-card done"><p>Все шаги по вашим отметкам выполнены. Если появятся новые документы, обновите статус отметки.</p></div>
            )}

            <p className="label" style={{ margin: "18px 0 6px" }}>Отметки</p>
            {список.map((з) => (
              <div key={з.ид} className="mark">
                <Link href={`/a/${з.ид}`} className="mark-t"><b>ст. {з.ид}</b><span>{коротко(названия[з.ид] ?? "статья Расписания", 90)}</span></Link>
                <div className="mark-row">
                  <span className="mark-date">{дата(з.в)}{з.шагЗакрыт ? " · шаг выполнен" : ""}</span>
                  <button
                    className={`stat ${з.статус === "врач" ? "ok" : ""}`}
                    onClick={() => setДело(изменитьОтметку(з.ид, { статус: з.статус === "врач" ? "слово" : "врач", шагЗакрыт: false }))}
                  >
                    {з.статус === "врач" ? "от врача" : "со слов"}
                  </button>
                  <button className="rm" aria-label="Убрать из дела" onClick={() => setДело(убратьИзДела(з.ид))}>✕</button>
                </div>
              </div>
            ))}

            <p className="label" style={{ margin: "20px 0 6px" }}>Бланки, которые пригодятся</p>
            <Link href="/b/0" className="row"><b>Заявление</b><span>О выдаче копии решения призывной комиссии</span></Link>
            <Link href="/b/1" className="row"><b>Заявление</b><span>О направлении на дополнительное обследование</span></Link>
            <Link href="/b/3" className="row"><b>Заявление</b><span>О выдаче медицинских документов</span></Link>
          </>
        )}
      </div>
    </div>
  );
}
