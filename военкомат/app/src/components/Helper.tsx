"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  забытьКлюч, записатьНастройку, настройкаПоУмолчанию, проверитьКлюч, списокПровайдеров, ход, читатьНастройку,
  type Настройка, type ОтветХода, type Провайдер,
} from "@/lib/помощник";

type ТГ = { BackButton?: { show: () => void; hide: () => void; onClick: (f: () => void) => void; offClick: (f: () => void) => void } };
type Сообщение = { кто: "я" | "ядро"; текст: string; ответ?: ОтветХода };

const новаяСессия = () => "h" + Math.random().toString(36).slice(2, 10);

/* Помощник α: чат с ядром NNL. Без ключа отвечает само ядро (по тексту Расписания), со своим ключом подключается ваша модель. */
export default function Helper() {
  const роутер = useRouter();
  const [н, setН] = useState<Настройка>(настройкаПоУмолчанию());
  const [готово, setГотово] = useState(false);
  const [настройки, setНастройки] = useState(false);
  const [провайдеры, setПровайдеры] = useState<Провайдер[] | null>(null);
  const [модели, setМодели] = useState<string[]>([]);
  const [проверка, setПроверка] = useState<string>("");
  const [чат, setЧат] = useState<Сообщение[]>([]);
  const [текст, setТекст] = useState("");
  const [ждём, setЖдём] = useState(false);
  const сессия = useRef(новаяСессия());
  const конец = useRef<HTMLDivElement>(null);
  const назад = () => (window.history.length > 1 ? роутер.back() : роутер.push("/"));

  useEffect(() => {
    setН(читатьНастройку()); setГотово(true);
    списокПровайдеров().then(setПровайдеры).catch(() => setПровайдеры([]));
    const кн = (window as unknown as { Telegram?: { WebApp?: ТГ } }).Telegram?.WebApp?.BackButton;
    if (!кн) return;
    кн.show(); кн.onClick(назад);
    return () => { кн.offClick(назад); кн.hide(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { конец.current?.scrollIntoView({ block: "end" }); }, [чат, ждём]);

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

  const отправить = async () => {
    const т = текст.trim();
    if (!т || ждём) return;
    setТекст(""); setЖдём(true);
    setЧат((ч) => [...ч, { кто: "я", текст: т }]);
    try {
      const о = await ход(сессия.current, т, н);
      setЧат((ч) => [...ч, { кто: "ядро", текст: о.ответ, ответ: о }]);
    } catch (е) {
      setЧат((ч) => [...ч, { кто: "ядро", текст: `Не получилось: ${(е as Error).message}` }]);
    } finally {
      setЖдём(false);
    }
  };

  const подпись = н.режим === "свой" && н.ключ ? `NNL + ${н.провайдер} · ${н.модель}` : "Только ядро NNL · без ключа и модели";
  const выбранный = провайдеры?.find((п) => п.имя === н.провайдер);

  return (
    <div className="app">
      <header className="artbar">
        <button className="back" onClick={назад} aria-label="Назад">‹ Назад</button>
        <span>Помощник <em className="alpha">α</em></span>
        <button className="back" style={{ textAlign: "right" }} onClick={() => setНастройки(!настройки)}>{настройки ? "Чат" : "Ключ"}</button>
      </header>

      {настройки ? (
        <div className="scroll art">
          <h1 className="art-title">Подключить свою модель</h1>
          <p className="cnote">Без ключа помощник отвечает сам: ядро читает ваши слова и ищет статьи по тексту Расписания. Со своим ключом к ядру подключается модель, которую выберете вы. Ключ хранится только на этом устройстве, на сервере не сохраняется.</p>

          <section className="calc">
            <label className="pfield"><span>Провайдер</span>
              <select value={н.провайдер} onChange={(е) => { менять({ провайдер: е.target.value, модель: "" }); setМодели([]); setПроверка(""); }}>
                <option value="">— выберите —</option>
                {(провайдеры ?? []).map((п) => <option key={п.имя} value={п.имя}>{п.имя}</option>)}
              </select>
            </label>
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
            {н.режим === "свой" ? <button className="add ghost" style={{ marginTop: 12 }} onClick={() => { забытьКлюч(); setН(читатьНастройку()); setМодели([]); setПроверка("Ключ удалён с устройства."); }}>Забыть ключ</button> : null}
          </section>
          <button className="add" style={{ marginTop: 14 }} onClick={() => setНастройки(false)}>К чату</button>
        </div>
      ) : (
        <>
          <div className="scroll art chat">
            <p className="cnote" style={{ textAlign: "center" }}>{готово ? подпись : ""}</p>
            {!чат.length ? (
              <div className="empty">
                <h3>Опишите, что беспокоит</h3>
                <p>Своими словами: «давление 160 на 100», «минус 6 на оба глаза», «болит колено после травмы». Ядро найдёт статью и объяснит, какие документы нужны.</p>
              </div>
            ) : null}
            {чат.map((с, i) => (
              <div key={i} className={`msg ${с.кто === "я" ? "me" : "bot"}`}>
                <div className="bub">{с.текст}</div>
                {с.ответ?.ссылки?.length ? (
                  <div className="refs">
                    {с.ответ.ссылки.filter((с2) => с2.ок).map((с2) => (
                      <Link key={с2.статья + (с2.пункт ?? "")} href={`/a/${с2.статья}`} className="ref">ст. {с2.статья}{с2.пункт ? ` п. «${с2.пункт}»` : ""}{с2.название ? ` · ${с2.название.slice(0, 40)}` : ""}</Link>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
            {ждём ? <div className="msg bot"><div className="bub dots-load">Разбираю…</div></div> : null}
            <div ref={конец} />
          </div>
          <form className="chat-bar" onSubmit={(е) => { е.preventDefault(); отправить(); }}>
            <input value={текст} onChange={(е) => setТекст(е.target.value)} placeholder="Опишите, что беспокоит" autoComplete="off" enterKeyHint="send" aria-label="Сообщение" />
            <button type="submit" disabled={ждём || !текст.trim()} aria-label="Отправить">↑</button>
          </form>
        </>
      )}
    </div>
  );
}
