/* Обращения к Python-ядру NNL. Адрес /api переписывает next.config.ts. */
export type Кандидат = { ид: string; название: string; p: number; p_показ?: number; пункт?: string };
export type Ответ = {
  запрос: string;
  статьи?: Кандидат[];
  предложения?: { текст: string; статья: string; p: number }[];
  расшифровано?: { сокращение: string; значение: string }[];
  подсказка?: string;
  вне_темы?: boolean;
};

export async function умныйПоиск(q: string, сигнал?: AbortSignal): Promise<Ответ> {
  const р = await fetch(`/api/${encodeURIComponent("умныйпоиск")}?q=${encodeURIComponent(q)}`, { signal: сигнал });
  if (!р.ok) throw new Error(`ядро ответило ${р.status}`);
  return р.json();
}
