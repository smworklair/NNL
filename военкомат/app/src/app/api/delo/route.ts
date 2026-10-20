import { neon } from "@neondatabase/serverless";
import { проверитьInitData } from "@/lib/telegram-auth";

/* «Моё дело» на сервере. Каждый запрос подписан Telegram: читаем и пишем только данные того, кто подписал. */
export const dynamic = "force-dynamic";

const ответ = (тело: unknown, статус = 200) => Response.json(тело, { status: статус, headers: { "Cache-Control": "no-store" } });

async function кто(req: Request) {
  const токен = process.env.TELEGRAM_BOT_TOKEN;
  if (!токен || !process.env.DATABASE_URL) return { ошибка: ответ({ ошибка: "сервер не настроен" }, 503) };
  const данные = req.headers.get("x-telegram-init-data");
  if (!данные) return { ошибка: ответ({ ошибка: "нужен Telegram" }, 401) };
  const п = проверитьInitData(данные, токен);
  if (!п) return { ошибка: ответ({ ошибка: "подпись не подошла" }, 401) };
  return { id: п.id, sql: neon(process.env.DATABASE_URL) };
}

export async function GET(req: Request) {
  const к = await кто(req);
  if (к.ошибка) return к.ошибка;
  const строки = await к.sql`select article_id as ид, status as статус, extract(epoch from added_at) * 1000 as в, step_closed as "шагЗакрыт"
    from delo where tg_id = ${к.id} order by added_at desc`;
  return ответ(строки.map((с) => ({ ид: с.ид, статус: с.статус, в: Math.round(Number(с.в)), шагЗакрыт: с.шагЗакрыт })));
}

export async function POST(req: Request) {
  const к = await кто(req);
  if (к.ошибка) return к.ошибка;
  const тело = (await req.json().catch(() => null)) as { ид?: string; статус?: string; шагЗакрыт?: boolean } | null;
  const ид = String(тело?.ид ?? "");
  const статус = тело?.статус === "врач" ? "врач" : "слово";
  const шаг = typeof тело?.шагЗакрыт === "boolean" ? тело.шагЗакрыт : null;
  if (!/^\d{1,2}$/.test(ид) || Number(ид) < 1 || Number(ид) > 88) return ответ({ ошибка: "нет такой статьи" }, 400);
  await к.sql`insert into users (tg_id) values (${к.id}) on conflict do nothing`;
  await к.sql`insert into delo (tg_id, article_id, status, step_closed) values (${к.id}, ${ид}, ${статус}, ${шаг ?? false})
    on conflict (tg_id, article_id) do update set status = excluded.status,
      step_closed = coalesce(${шаг}::boolean, delo.step_closed)`;
  return ответ({ ок: true });
}

export async function DELETE(req: Request) {
  const к = await кто(req);
  if (к.ошибка) return к.ошибка;
  const ид = new URL(req.url).searchParams.get("ид") ?? "";
  await к.sql`delete from delo where tg_id = ${к.id} and article_id = ${ид}`;
  return ответ({ ок: true });
}
