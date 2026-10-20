// Применяет db/schema.sql к базе из DATABASE_URL_UNPOOLED (или DATABASE_URL). Запуск: node --env-file=.env.local db/migrate.mjs
import { readFileSync } from "node:fs";
import { neon } from "@neondatabase/serverless";

const url = process.env.DATABASE_URL_UNPOOLED || process.env.DATABASE_URL;
if (!url) throw new Error("нет DATABASE_URL: выполните vercel env pull .env.local");
const sql = neon(url);
const части = readFileSync(new URL("./schema.sql", import.meta.url), "utf8").split(/;\s*\n/).map((с) => с.replace(/^\s*--.*$/gm, "").trim()).filter(Boolean);
for (const ч of части) await sql.query(ч);
const таблицы = await sql.query("select table_name from information_schema.tables where table_schema = 'public' order by 1");
console.log("таблицы:", таблицы.map((т) => т.table_name).join(", "));
