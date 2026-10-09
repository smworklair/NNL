import json, zlib, base64, time, re
import kaggle_benchmarks as kbench
NL = chr(10)
D = json.loads(zlib.decompress(base64.b64decode("@@DATA@@")).decode("utf-8"))
H = NL.join(a["id"] + " - " + a["название"] for a in D["health_articles"])
L = NL.join(t["id"] + " - " + t["название"] for t in D["law_topics"])
SYS = NL.join([
    "Ты помощник призывника в России. Тебе дают вопрос человека. Определи область:",
    "здоровье - спрашивают, возьмут ли в армию / какая категория годности при болезни, травме, диагнозе (ответ - номер статьи Расписания болезней);",
    "право - призыв, повестки, отсрочки, воинский учёт, документы военкомата, обжалование, медкомиссия как процедура (ответ - id правовой темы);",
    "вне - всё остальное (тогда id пустой).",
    "", "СТАТЬИ РАСПИСАНИЯ БОЛЕЗНЕЙ:", H, "", "ПРАВОВЫЕ ТЕМЫ:", L, "",
    'Ответь ТОЛЬКО одной строкой JSON: {"область": "здоровье|право|вне", "id": "номер статьи или id темы или пусто"}'])
RX = re.compile("[{].*[}]", re.S)

def ask(llm, q):
    t = time.time()
    r = llm.prompt(SYS + NL + NL + "ВОПРОС: " + q)
    dt = time.time() - t
    m = RX.search(str(r))
    try:
        a = json.loads(m.group(0)) if m else {}
    except Exception:
        a = {}
    return a, dt

RES = {}
def score(name, n=50):
    llm = kbench.llms[name]
    ok_area = ok_ans = n_ans = 0
    times, rows = [], []
    for q in D["questions"][:n]:
        try:
            a, dt = ask(llm, q["text"])
        except Exception as e:
            a, dt = {"ошибка": str(e)[:200]}, 0.0
        times.append(dt)
        got = a.get("область", "вне")
        ok_area += (q["area"] == "спорно") or (got == q["area"])
        if q["area"] in ("здоровье", "право") and q["answers"]:
            n_ans += 1
            ok_ans += got == q["area"] and str(a.get("id", "")) in q["answers"]
        rows.append({"i": q["i"], "ответ": a, "сек": round(dt, 2)})
    times.sort()
    RES[name] = {"область": ok_area, "из": n, "ответ": ok_ans, "из_с_ответом": n_ans, "медиана_сек": round(times[len(times) // 2], 2), "строки": rows}
    print(name, "| область", ok_area, "/", n, "| статья/тема", ok_ans, "/", n_ans, "| медиана", RES[name]["медиана_сек"], "с", flush=True)

MODELS = ["google/gemini-3.8-flash", "anthropic/claude-haiku-4-5@20251001", "openai/gpt-6-luna", "anthropic/claude-sonnet-5-5@default"]
for m in MODELS:
    score(m)
json.dump(RES, open("/kaggle/working/nnl_flagships.json", "w"), ensure_ascii=False)
