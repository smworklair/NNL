# -*- coding: utf-8 -*-
"""Скачивает документ с открытой версии consultant.ru по разделам (как видит браузер без подписки), с паузами.
Сохраняет сырой HTML и очищенный текст каждого раздела + общий текст. Запуск: python скачать_консультант.py <cons_doc_LAW_id> <папка>"""
import html, json, os, re, sys, time, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
DOC, OUT = sys.argv[1], sys.argv[2]
os.makedirs(os.path.join(OUT, "html"), exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"}

def get(url):
    for k in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read().decode("utf-8", "replace")
        except Exception as e:
            time.sleep(5 * (k + 1)); err = e
    raise err

def text(h):
    h = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    m = re.search(r'<div[^>]+class="[^"]*document-page__content[^"]*"', h)
    if m: h = h[m.start():]
    t = re.sub(r"<br\s*/?>|</p>|</div>|</tr>|</h\d>", "\n", h)
    t = re.sub(r"</t[dh]>", " | ", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    t = re.sub(r"[ \t\xa0]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()

base = "https://www.consultant.ru/document/%s/" % DOC
top = get(base)
title = re.search(r"<title>(.*?)</title>", top, re.S).group(1).strip()
ids, seen = [], set()
for m in re.finditer(r'href="/document/%s/([0-9a-f]{20,})/?[^"]*"[^>]*>(.*?)</a>' % DOC, top, re.S):
    i = m.group(1)
    if i not in seen:
        seen.add(i); ids.append((i, html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()))
print(title, "| разделов:", len(ids), flush=True)
parts = []
for n, (i, name) in enumerate(ids):
    h = get(base + i + "/")
    open(os.path.join(OUT, "html", "%03d_%s.html" % (n, i)), "w", encoding="utf-8").write(h)
    parts.append({"n": n, "id": i, "раздел": name, "текст": text(h)})
    print(n, name[:70], len(parts[-1]["текст"]), flush=True)
    time.sleep(1.5)
json.dump({"документ": title, "url": base, "скачано": time.strftime("%Y-%m-%d %H:%M"), "разделы": parts},
          open(os.path.join(OUT, "разделы.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
with open(os.path.join(OUT, "текст.txt"), "w", encoding="utf-8") as f:
    f.write(title + "\n" + base + "\n\n")
    for p in parts:
        f.write("\n\n##### " + p["раздел"] + "\n" + p["текст"])
print("готово", OUT)
