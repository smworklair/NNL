# -*- coding: utf-8 -*-
"""Клинические рекомендации Минздрава (apicr.minzdrav.gov.ru, открытый API рубрикатора cr.minzdrav.gov.ru).
Берёт действующие (Status 0) рекомендации для взрослых по болезням, которые встречаются в вопросах призывников и в Расписании болезней,
сохраняет текст разделов без картинок: кр/<код>.txt и сводку кр/сводка.json. Запуск: python скачать_кр.py"""
import html, json, os, re, sys, time, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "кр")
KEYS = (r"гипертенз|гипертон|диабет|ожирен|астм|миоп|плоск|деформац\w* стоп|сколиоз|язвенн\w* болезн|туберкул|гепатит|эпилеп|псориаз|"
        r"бронхит|гастрит|дорсопат|остеохондр|грыж|варикоц|энурез|заикан|депресс|тревожн|шизофр|аллергическ\w* ринит|тахикард|аритм|"
        r"брадиаритм|пиелонеф|гломерул|мочекам|геморро|кератоконус|глауком|косоглаз|тугоух|синусит|ринит|сердечн\w* недостат|"
        r"ишемическ|вич|кардиомиопат|расстройств\w* личности|умственн|аутизм|расстройств\w* аутистич|недостаточность питания|"
        r"гипотиреоз|тиреотоксикоз|узлов\w* зоб|деформац\w* нижн|нарушени\w* рефракц|экзем|атопическ|акне|варикоз|колит|болезнь крона|"
        r"панкреатит|желчнокам|холецист|мигрен|головн\w* бол|черепно-мозг|последстви\w* травм|переломы|остеомиелит|артрит|артроз|плоскостоп")
UA = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}

def get(url):
    for k in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read().decode("utf-8")
        except Exception as e:
            err = e; time.sleep(5 * (k + 1))
    raise err

def clean(h):
    h = re.sub(r'<img[^>]*>', ' [рисунок] ', h or "")
    h = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    t = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</tr>|</h\d>", "\n", h)
    t = re.sub(r"</t[dh]>", " | ", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    t = re.sub(r"[ \t\xa0]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()

L = json.load(open(os.path.join(OUT, "список_всех_кр.json"), encoding="utf-8"))["Data"]
pick = [x for x in L if x.get("Status") == 0 and x.get("Name") and (x.get("AgeCategoryStr") or "") != "Дети" and re.search(KEYS, x["Name"], re.I)]
print("к скачиванию:", len(pick), flush=True)
summary = []
for x in pick:
    cv = x["CodeVersion"]
    p = os.path.join(OUT, cv + ".txt")
    if not os.path.exists(p):
        d = json.loads(get("https://apicr.minzdrav.gov.ru/api.ashx?op=GetClinrec2&id=%s&ssid=null" % cv))
        secs = (d.get("obj") or {}).get("sections") or []
        with open(p, "w", encoding="utf-8") as f:
            f.write("%s\nКР %s, утверждена %s, размещена %s, МКБ: %s\nhttps://cr.minzdrav.gov.ru/preview-cr/%s\n" % (
                x["Name"].strip(), cv, d.get("approved") or "", x.get("PublishDateStr", "")[:10], ", ".join(m["MkbCode"] for m in x.get("Mkbs") or []), cv))
            for s in secs:
                f.write("\n\n##### " + clean(s.get("title") or "") + "\n" + clean(s.get("content") or ""))
        time.sleep(1.0)
    summary.append({"код": cv, "название": x["Name"].strip(), "размещена": x.get("PublishDateStr", "")[:10],
                    "мкб": [m["MkbCode"] for m in x.get("Mkbs") or []], "файл": cv + ".txt", "символов": os.path.getsize(p)})
    print(cv, x["Name"][:70], summary[-1]["символов"], flush=True)
json.dump(summary, open(os.path.join(OUT, "сводка.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("готово:", len(summary))
