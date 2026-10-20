import { createHmac, timingSafeEqual } from "node:crypto";

/* Проверка подписи Telegram Mini App (initData): доказывает, что запрос пришёл из Telegram и tg_id настоящий.
   Алгоритм из документации Telegram: секрет = HMAC_SHA256("WebAppData", токен бота), подпись = HMAC_SHA256(секрет, строка проверки). */
export type Пользователь = { id: number; first_name?: string; username?: string };

export function проверитьInitData(initData: string, токен: string, срокСек = 86400): Пользователь | null {
  const параметры = new URLSearchParams(initData);
  const хеш = параметры.get("hash");
  if (!хеш || !/^[0-9a-f]{64}$/i.test(хеш)) return null;
  параметры.delete("hash");
  const строка = [...параметры.entries()].sort(([а], [б]) => (а < б ? -1 : 1)).map(([к, з]) => `${к}=${з}`).join("\n");
  const секрет = createHmac("sha256", "WebAppData").update(токен).digest();
  const ожидаемый = createHmac("sha256", секрет).update(строка).digest();
  const полученный = Buffer.from(хеш, "hex");
  if (полученный.length !== ожидаемый.length || !timingSafeEqual(полученный, ожидаемый)) return null;
  const дата = Number(параметры.get("auth_date"));
  if (!дата || Date.now() / 1000 - дата > срокСек) return null;
  try {
    const п = JSON.parse(параметры.get("user") ?? "null");
    return п && typeof п.id === "number" ? (п as Пользователь) : null;
  } catch {
    return null;
  }
}
