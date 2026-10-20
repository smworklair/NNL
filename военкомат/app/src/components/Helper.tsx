"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Modes from "./Modes";
import { добавитьВДело, естьВДеле } from "@/lib/дело";
import { заглавиеЧата, очиститьЧаты, сохранитьЧат, удалитьЧат, читатьЧаты, type Чат, type Сообщение } from "@/lib/чаты";
import {
  забытьКлюч, записатьНастройку, настройкаПоУмолчанию, проверитьКлюч, списокПровайдеров, ход, читатьНастройку,
  type Настройка, type Провайдер,
} from "@/lib/помощник";

type ТГ = { BackButton?: { show: () => void; hide: () => void; onClick: (f: () => void) => void; offClick: (f: () => void) => void } };
type Экран = "чат" | "ключ" | "история";

const ПРИМЕРЫ = [
  { п: "Окулист после капель: −7", т: "Окулист после капель написал: близорукость −7 дптр на оба глаза." },
  { п: "Сам решил, что минус семь", т: "Сам решил, что у меня минус семь, к окулисту не ходил." },
  { п: "Давление дома 150/95", т: "Давление дома 150 на 95, мерил сам тонометром." },
];

const новаяСессия = () => "h" + Math.random().toString(36).slice(2, 10);

/* Помощник α: чат с ядром NNL. Без ключа отвечает само ядро (по тексту Расписания), со своим ключом подключается ваша модель. */
export default function Helper() {
  const роутер = useRouter();
  const [н, setН] = useState<Настройка>(настройкаПоУмолчанию());
  const [готово, setГотово] = useState(false);
  const [экран, setЭкран] = useState<Экран>("чат");
  const [история, setИстория] = useState<Чат[]>([]);
  const [раскрыто, setРаскрыто] = useState<Record<number, boolean>>({});
  const [пояснить, setПояснить] = useState(false);
  const [тикДела, setТикДела] = useState(0);
  const [провайдеры, setПровайдеры] = useState<Провайдер[] | null>(null);
  const [модели, setМодели] = useState<string[]>([]);
  const [проверка, setПроверка] = useState<string>("");
  const [чат, setЧат] = useState<Сообщение[]>([]);
  const [текст, setТекст] = useState("");
  const [ждём, setЖдём] = useState(false);
  const сессия = useRef(новаяСессия());
  const конец = useRef<HTMLDivElement>(null);
  const назадРеф = useRef<() => void>(() => {});
  назадРеф.current = () => {
    if (экран !== "чат") setЭкран("чат");
    else if (window.history.length > 1) роутер.back();
    else роутер.push("/");
  };

  useEffect(() => {
    setН(читатьНастройку()); setГотово(true);
    списокПровайдеров().then(setПровайдеры).catch(() => setПровайдеры([]));
    const кн = (window as unknown as { Telegram?: { WebApp?: ТГ } }).Telegram?.WebApp?.BackButton;
    if (!кн) return;
    const f = () => назадРеф.current();
    кн.show(); кн.onClick(f);
    return () => { кн.offClick(f); кн.hide(); };
  }, []);
  useEffect(() => { конец.current?.scrollIntoView({ block: "end" }); }, [чат, ждём]);
  useEffect(() => { if (готово) сохранитьЧат(сессия.current, чат); }, [чат, готово]);

  const менять = (п: Partial<Настройка>) => { const н2 = { ...н, ...п }; setН(н2); записатьНастройку(н2); };

  const проверить = async () => {
    setПроверка("Проверяю ключ…"); setМодели([]);
    const р = await проверитьКлюч(н.провайдер, н.ключ.trim());
    if (р.ок && р.модели?.length) {
      setМодели(р.модели);
      const м = р.модели.includes(н.модель) ? н.модель : р.модели[0];
      менять({ режим: "свой", модель: м, ключ: н.ключ.trim() });
      setПроверка(`Ключ принят. Моделей: ${р.модели.length}. Ключ хранится только на этом устройстве.`);
    } else {
      setПроверка(р.ошибка || "Ключ не подошёл.");
    }
  };

  const отправить = async (из?: string) => {
    const т = (из ?? текст).trim();
    if (!т || ждём) return;
    if (из === undefined) setТекст("");
    setЖдём(true); setПояснить(false);
    setЧат((ч) => [...ч, { кто: "я", текст: т }]);
    try {
      const о = await ход(сессия.current, т, н);
      setЧат((ч) => [...ч, { кто: "ядро", текст: о.ответ, ответ: о }]);
    } catch (е) {
      setЧат((ч) => [...ч, { кто: "ядро", текст: `Не получилось ответить: ${(е as Error).message}`, ошибка: true, повтор: т }]);
    } finally {
      setЖдём(false);
    }
  };
  const ещёРаз = (с: Сообщение, i: number) => {
    if (!с.повтор) return;
    setЧат((ч) => ч.filter((м, k) => k !== i && !(k === i - 1 && м.кто === "я" && м.текст === с.повтор)));
    отправить(с.повтор);
  };
  const новыйЧат = () => {
    сохранитьЧат(сессия.current, чат);
    сессия.current = новаяСессия();
    setЧат([]); setРаскрыто({}); setПояснить(false); setТекст(""); setЭкран("чат");
  };
  const открытьИсторию = () => { setИстория(читатьЧаты()); setЭкран("история"); };
  const вернутьЧат = (ч: Чат) => {
    сохранитьЧат(сессия.current, чат);
    сессия.current = ч.ид; setЧат(ч.сообщения); setРаскрыто({}); setЭкран("чат");
  };

  const своя = н.режим === "свой" && !!н.ключ;
  const подпись = своя ? `NNL + ${н.провайдер} · ${н.модель}` : "Только ядро NNL · без ключа и модели";
  const выбранный = провайдеры?.find((п) => п.имя === н.провайдер);
  const последний = чат.length ? чат[чат.length - 1] : null;
  const спрашивает = !ждём && последний?.кто === "ядро" && !последний.ошибка && последний.ответ?.действие === "спросить" && !!последний.ответ?.вопрос?.текст;

  const пузырь = (с: Сообщение, i: number) => {
    if (с.кто === "я") return <div className="bub">{с.текст}</div>;
    const строки = с.текст.split("\n");
    const главное = (строки.shift() ?? "").trim();
    const пояснение = строки.join("\n").trim();
    const длинное = пояснение.length > 420;
    return (
      <div className="bub">
        {главное ? <p className="main">{главное}</p> : null}
        {пояснение ? <p className={`more ${длинное && !раскрыто[i] ? "clamp" : ""}`}>{пояснение}</p> : null}
        {длинное ? <button type="button" className="linkbtn" onClick={() => setРаскрыто({ ...раскрыто, [i]: !раскрыто[i] })}>{раскрыто[i] ? "Свернуть" : "Показать полностью"}</button> : null}
      </div>
    );
  };

  const карта = (
    <>
      <b>Подключение · {своя ? "своя модель" : "ядро NNL"}</b>
      <span>{готово ? подпись : ""}</span>
    </>
  );

  return (
    <div className="app" data-tick={тикДела}>
      <header className="artbar">
        <button className="back" onClick={() => назадРеф.current()} aria-label="Назад">‹ Назад</button>
        <span>{экран === "история" ? "История" : экран === "ключ" ? "Подключение" : <>Помощник <em className="alpha">α</em></>}</span>
        <button className="newchat" onClick={новыйЧат} aria-label="Новый чат">＋ Новый</button>
      </header>

      <div className="tools">
        <button type="button" className={`tool ${экран === "чат" ? "on" : ""}`} onClick={() => setЭкран("чат")}>Чат</button>
        <button type="button" className={`tool ${экран === "история" ? "on" : ""}`} onClick={открытьИсторию}>История</button>
        <button type="button" className={`tool ${экран === "ключ" ? "on" : ""}`} onClick={() => setЭкран("ключ")}>Подключение</button>
      </div>

      {экран === "ключ" ? (
        <div className="scroll art">
          <div className="pcard">{карта}</div>
          <h1 className="art-title" style={{ marginTop: 16 }}>Подключить свою модель</h1>
          <p className="cnote">Без ключа помощник отвечает сам: ядро читает ваши слова и ищет статьи по тексту Расписания. Со своим ключом к ядру подключается модель, которую выберете вы. Ключ хранится только на этом устройстве, на сервере не сохраняется.</p>

          <section className="calc">
            <label className="pfield"><span>Провайдер</span>
              <select value={н.провайдер} onChange={(е) => { менять({ провайдер: е.target.value, модель: "" }); setМодели([]); setПроверка(""); }}>
                <option value="">— выберите —</option>
                {(провайдеры ?? []).map((п) => <option key={п.имя} value={п.имя}>{п.имя}</option>)}
              </select>
            </label>
            {провайдеры === null ? <p className="cnote">Загружаю список провайдеров…</p> : null}
            {провайдеры && !провайдеры.length ? <p className="cnote">Список провайдеров не загрузился. Проверьте интернет и откройте экран ещё раз.</p> : null}
            {выбранный?.документация ? <p className="cnote"><a href={выбранный.документация} target="_blank" rel="noopener noreferrer" style={{ textDecoration: "underline" }}>Где взять ключ</a></p> : null}
            <label className="pfield"><span>Ваш ключ</span>
              <input type="password" value={н.ключ} onChange={(е) => менять({ ключ: е.target.value })} autoComplete="off" spellCheck={false} placeholder="sk-…" />
            </label>
            <button className="add" style={{ marginTop: 12 }} disabled={!н.провайдер || !н.ключ.trim()} onClick={проверить}>Проверить ключ</button>
            {проверка ? <p className="cnote" style={{ marginTop: 8 }}>{проверка}</p> : null}
            {модели.length ? (
              <label className="pfield"><span>Модель</span>
                <select value={н.модель} onChange={(е) => менять({ модель: е.target.value })}>
                  {модели.map((м) => <option key={м} value={м}>{м}</option>)}
                </select>
              </label>
            ) : null}
            {н.режим === "свой" ? <button className="add ghost" style={{ marginTop: 12 }} onClick={() => { забытьКлюч(); setН(читатьНастройку()); setМодели([]); setПроверка("Ключ удалён с устройства. Помощник отвечает только ядром."); }}>Забыть ключ и вернуться к ядру</button> : null}
          </section>
          <button className="add" style={{ marginTop: 14 }} onClick={() => setЭкран("чат")}>К чату</button>
        </div>
      ) : экран === "история" ? (
        <div className="scroll art">
          <p className="cnote">Хранится только на этом устройстве, последние 12 разговоров.</p>
          {история.length ? история.map((ч) => (
            <div className="row-wrap" key={ч.ид}>
              <button type="button" className="row hist" onClick={() => вернутьЧат(ч)}>
                <span>{заглавиеЧата(ч)}</span>
                <em>{new Date(ч.в).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })} · {ч.сообщения.length} сообщ.</em>
              </button>
              <button type="button" className="rm" aria-label="Удалить разговор" onClick={() => { удалитьЧат(ч.ид); setИстория(читатьЧаты()); }}>✕</button>
            </div>
          )) : <div className="empty"><h3>Пока пусто</h3><p>Здесь появятся ваши разговоры с помощником.</p></div>}
          {история.length ? <button className="add ghost" style={{ marginTop: 14 }} onClick={() => { очиститьЧаты(); setИстория([]); }}>Очистить историю</button> : null}
        </div>
      ) : (
        <>
          <div className="scroll art chat">
            <button type="button" className="pcard link" onClick={() => setЭкран("ключ")}>
              {карта}
              <i>Настроить</i>
            </button>
            {!чат.length ? (
              <div className="empty">
                <h3>Опишите, что беспокоит</h3>
                <p>Своими словами, как рассказали бы другу. Сверю с Расписанием болезней и покажу, откуда берётся категория. Или начните с примера:</p>
                <div className="chips-wrap">{ПРИМЕРЫ.map((п) => <button key={п.п} type="button" className="chip" onClick={() => отправить(п.т)}>{п.п}</button>)}</div>
              </div>
            ) : null}
            {чат.map((с, i) => {
              const топ = с.ответ?.рейтинг?.[0];
              const показ = с.кто === "ядро" && !с.ошибка && !!топ && Number(топ.p) >= 0.05 && с.ответ?.действие !== "спросить";
              return (
                <div key={i} className={`msg ${с.кто === "я" ? "me" : "bot"}`}>
                  {пузырь(с, i)}
                  {с.ошибка ? (
                    <div className="qbtns">
                      <button type="button" className="q main" onClick={() => ещёРаз(с, i)}>Попробовать ещё раз</button>
                      {своя ? <button type="button" className="q" onClick={() => setЭкран("ключ")}>Проверить подключение</button> : null}
                    </div>
                  ) : null}
                  {показ && топ ? (
                    <div className="qbtns">
                      <Link href={`/a/${топ.статья}`} className="q main">Открыть ст. {топ.статья}</Link>
                      <button type="button" className="q" onClick={() => { добавитьВДело(String(топ.статья)); setТикДела(тикДела + 1); }}>{естьВДеле(String(топ.статья)) ? "В моём деле ✓" : "В моё дело"}</button>
                    </div>
                  ) : null}
                  {с.ответ?.ссылки?.length ? (
                    <div className="refs">
                      {с.ответ.ссылки.filter((с2) => с2.ок).map((с2) => (
                        <Link key={с2.статья + (с2.пункт ?? "")} href={`/a/${с2.статья}`} className="ref">ст. {с2.статья}{с2.пункт ? ` п. «${с2.пункт}»` : ""}{с2.название ? ` · ${с2.название.slice(0, 40)}` : ""}</Link>
                      ))}
                    </div>
                  ) : null}
                  {i === чат.length - 1 && спрашивает ? (
                    <>
                      <div className="qbtns">
                        <button type="button" className="q main" onClick={() => отправить("Да")}>Да</button>
                        <button type="button" className="q" onClick={() => отправить("Нет")}>Нет</button>
                        <button type="button" className="q" onClick={() => отправить("Не знаю")}>Не знаю</button>
                        <button type="button" className="q quiet" onClick={() => setПояснить(!пояснить)}>Объясните</button>
                      </div>
                      {пояснить ? <p className="cnote">Вопрос по статье {с.ответ?.вопрос?.статья}: от ответа зависит, какая графа Расписания подойдёт. Если не знаете, так и ответьте, это нормально.</p> : null}
                    </>
                  ) : null}
                </div>
              );
            })}
            {ждём ? <div className="msg bot"><div className="bub dots-load">Разбираю…</div></div> : null}
            <div ref={конец} />
          </div>
          <form className="chat-bar" onSubmit={(е) => { е.preventDefault(); отправить(); (document.activeElement as HTMLElement | null)?.blur(); }}>
            <input value={текст} onChange={(е) => setТекст(е.target.value)} placeholder="Опишите, что беспокоит" autoComplete="off" enterKeyHint="send" aria-label="Сообщение" />
            <button type="button" className="hide-kb" onClick={() => (document.activeElement as HTMLElement | null)?.blur()} aria-label="Скрыть клавиатуру">⌄</button>
            <button type="submit" disabled={ждём || !текст.trim()} aria-label="Отправить">↑</button>
          </form>
        </>
      )}
      <div className="dock-modes"><Modes активный="helper" /></div>
    </div>
  );
}
