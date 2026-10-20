"use client";
import { useEffect, useRef, useState } from "react";

/* Калькуляторы порогов: статьи 13, 40, 86 (спецификацию и расчёт отдаёт сервер, пороги читаются из текста статьи) и 34 (зрение).
   Страница чисел не знает: она рисует поля и показывает ответ ядра. */

type Поле =
  | { ключ: string; тип: "число"; подпись: string; мин: number; макс: number; шаг: number; ед: string; знач: number; ноль?: string }
  | { ключ: string; тип: "переключатель"; подпись: string; знач: boolean };
type Спецификация = { заголовок: string; подпись: string; поля: Поле[]; ид: string };
type Результат = {
  пункт: string | null; категория: string | null; итог: string; почему: string; подсветить?: string[];
  метрика?: { подпись: string; значение: string };
};
type Диапазон = { более: number; до: number | null; пункт: string; категория: string };

export type Подсветка = { буквы: string[]; категория: string | null };

const буквуГрафы = (к: string | null) => (к ? к.replace(/-.*$/, "") : "");
const число = (п: Поле & { тип: "число" }, v: number) => (v === 0 && п.ноль ? п.ноль : String(v).replace(".", ","));

function Итог({ р, пусто }: { р: Результат | null; пусто?: boolean }) {
  if (пусто || !р) {
    return (
      <div className="calc-res empty">
        <i>?</i>
        <div><b>Укажите своё значение</b><span>Двигайте ползунок, и здесь появится пункт статьи и категория.</span></div>
      </div>
    );
  }
  const к = буквуГрафы(р.категория);
  return (
    <div className={`calc-res ${к ? "k-" + к : ""}`}>
      <i>{р.категория ?? "—"}</i>
      <div>
        <b>{р.метрика ? `${р.метрика.подпись} ${р.метрика.значение} · ` : ""}{р.итог}{р.категория ? ` → категория ${р.категория}` : ""}</b>
        <span>{р.почему}</span>
      </div>
    </div>
  );
}

/* Статьи 13, 40, 86: поля и расчёт с сервера */
export function Calculator({ ид, при }: { ид: string; при: (п: Подсветка) => void }) {
  const [спец, setСпец] = useState<Спецификация | null>(null);
  const [знач, setЗнач] = useState<Record<string, number | boolean>>({});
  const [тронут, setТронут] = useState(false);
  const [рез, setРез] = useState<Результат | null>(null);
  const [сбой, setСбой] = useState(false);
  const номер = useRef(0);

  useEffect(() => {
    fetch(`/api/${encodeURIComponent("пороги")}?ид=${encodeURIComponent(ид)}`)
      .then((р) => { if (!р.ok) throw new Error(); return р.json() as Promise<{ спецификация: Спецификация }>; })
      .then((д) => {
        setСпец(д.спецификация);
        setЗнач(Object.fromEntries(д.спецификация.поля.map((п) => [п.ключ, п.знач])));
      })
      .catch(() => setСбой(true));
  }, [ид]);

  useEffect(() => {
    if (!спец || !тронут) { при({ буквы: [], категория: null }); return; }
    const мой = ++номер.current;
    const параметры = new URLSearchParams({ ид });
    спец.поля.forEach((п) => параметры.set(п.ключ, п.тип === "переключатель" ? (знач[п.ключ] ? "1" : "0") : String(знач[п.ключ])));
    const таймер = setTimeout(() => {
      fetch(`/api/${encodeURIComponent("пороги")}?${параметры}`)
        .then((р) => р.json() as Promise<{ результат?: Результат }>)
        .then((д) => {
          if (мой !== номер.current || !д.результат) return;
          setРез(д.результат);
          при({ буквы: д.результат.подсветить ?? [], категория: д.результат.категория });
        })
        .catch(() => {});
    }, 120);
    return () => clearTimeout(таймер);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [знач, тронут, спец, ид]);

  if (сбой) return null;
  if (!спец) return <section className="calc"><p className="note">Загружаю калькулятор…</p></section>;
  return (
    <section className="calc">
      <h3>{спец.заголовок}</h3>
      <p className="cnote">{спец.подпись}</p>
      {спец.поля.map((п) =>
        п.тип === "переключатель" ? (
          <label key={п.ключ} className="switch">
            <input type="checkbox" checked={!!знач[п.ключ]} onChange={(е) => { setТронут(true); setЗнач({ ...знач, [п.ключ]: е.target.checked }); }} />
            <span>{п.подпись}</span>
          </label>
        ) : (
          <div key={п.ключ} className="cfield">
            <div className="cval"><b>{число(п, Number(знач[п.ключ]))}</b><span>{п.подпись} · {п.ед}</span></div>
            <input type="range" min={п.мин} max={п.макс} step={п.шаг} value={Number(знач[п.ключ])} aria-label={п.подпись}
              onChange={(е) => { setТронут(true); setЗнач({ ...знач, [п.ключ]: Number(е.target.value) }); }} />
          </div>
        ),
      )}
      <Итог р={рез} пусто={!тронут} />
    </section>
  );
}

/* Статья 34: близорукость в диоптриях по линейке порогов из текста статьи */
const ЗАПАСНЫЕ: Диапазон[] = [
  { более: 12, до: null, пункт: "а", категория: "Д" }, { более: 8, до: 12, пункт: "б", категория: "В" },
  { более: 6, до: 8, пункт: "в", категория: "В" }, { более: 3, до: 6, пункт: "г", категория: "Б-3" },
];

export function Myopia({ при }: { при: (п: Подсветка) => void }) {
  const [диап, setДиап] = useState<Диапазон[] | null>(null);
  const [v, setV] = useState(0);
  const [тронут, setТронут] = useState(false);

  useEffect(() => {
    fetch(`/api/${encodeURIComponent("ст34")}?${new URLSearchParams({ "дптр": "0" })}`)
      .then((р) => { if (!р.ok) throw new Error(); return р.json() as Promise<{ диапазоны: Диапазон[] }>; })
      .then((д) => setДиап(д.диапазоны))
      .catch(() => setДиап(ЗАПАСНЫЕ));
  }, []);

  const п = диап?.find((д) => v > д.более && (д.до === null || v <= д.до)) ?? null;
  useEffect(() => {
    при(тронут && п ? { буквы: [п.пункт], категория: п.категория } : { буквы: [], категория: null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [v, тронут, диап]);

  return (
    <section className="calc">
      <h3>Близорукость: сколько диоптрий?</h3>
      <p className="cnote">Берётся худший глаз по модулю. Пороги читаются из текста статьи.</p>
      <div className="cfield">
        <div className="cval"><b>{!тронут ? "—" : v === 0 ? "0" : `−${v.toFixed(1).replace(".", ",")}`}</b><span>Диоптрии · дптр</span></div>
        <input type="range" min={0} max={16} step={0.5} value={v} aria-label="Диоптрии"
          onChange={(е) => { setТронут(true); setV(Number(е.target.value)); }} />
      </div>
      {!тронут ? <Итог р={null} пусто /> : п ? (
        <Итог р={{ пункт: п.пункт, категория: п.категория, итог: `Пункт «${п.пункт}»`, почему: `Более ${String(п.более).replace(".", ",")}${п.до ? ` и до ${String(п.до).replace(".", ",")}` : ""} дптр.` }} />
      ) : (
        <div className="calc-res"><i>—</i><div><b>Ниже порога этой статьи</b><span>Меньше 3 дптр: по этой статье ограничений нет.</span></div></div>
      )}
    </section>
  );
}
