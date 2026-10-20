import Link from "next/link";

type Режим = "home" | "invest" | "helper";

/* Переключатель режима внизу экрана: «Справочник» (главная), «Расследование» (проверка комплекта документов), «Помощник α» (чат). */
export default function Modes({ активный }: { активный: Режим }) {
  const п = (р: Режим, href: string, текст: React.ReactNode) => (
    <Link href={href} className={`mode ${активный === р ? "on" : ""}`} aria-current={активный === р ? "page" : undefined}>{текст}</Link>
  );
  return (
    <div className="modes" role="group" aria-label="Режим">
      {п("home", "/", "Справочник")}
      {п("invest", "/investigate", "Расследование")}
      {п("helper", "/helper", <>Помощник<em>α</em></>)}
    </div>
  );
}
