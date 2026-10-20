import Link from "next/link";

/* Переключатель режима внизу экрана: «Расследование» (главная) и «Помощник α» (чат). Компактный, в одну строку. */
export default function Modes({ активный }: { активный: "home" | "helper" }) {
  return (
    <div className="modes" role="group" aria-label="Режим">
      <Link href="/" className={`mode ${активный === "home" ? "on" : ""}`}>Расследование</Link>
      <Link href="/helper" className={`mode ${активный === "helper" ? "on" : ""}`}>Помощник<em>α</em></Link>
    </div>
  );
}
