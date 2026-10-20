import Link from "next/link";

/* Переключатель режима внизу экрана, как в старом сайте: «Расследование» (справочник на главной) и «Помощник α» (чат). */
export default function Modes({ активный }: { активный: "home" | "helper" }) {
  return (
    <div className="modes" role="group" aria-label="Режим">
      <Link href="/" className={`mode ${активный === "home" ? "on" : ""}`} aria-current={активный === "home" ? "page" : undefined}>Расследование</Link>
      <Link href="/helper" className={`mode ${активный === "helper" ? "on" : ""}`} aria-current={активный === "helper" ? "page" : undefined}>Помощник<em>α</em></Link>
    </div>
  );
}
