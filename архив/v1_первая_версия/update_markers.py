# -*- coding: utf-8 -*-
"""Обновить ТОЛЬКО маркеры в паспортах (веса/словари/знания не трогать).

Маркеры — правило из текстов баз знаний, не обучены. Исправление: без
пред-капа most_common (учитываются все стемы с doc-freq>=2).
"""
import json
import os
import sys

sys.path.insert(0, r"C:\ЯДРО-ОПЫТ\v1")
sys.path.insert(0, r"C:\ЯДРО-ОПЫТ\v1\ядро")
import train_blocks as T

BZ = r"C:\ЯДРО-ОПЫТ\v1\блоки\zdorovie"
BP = r"C:\ЯДРО-ОПЫТ\v1\блоки\pravo"


def main():
    kn_h, _ = T.build_knowledge_health()
    kn_l, _ = T.build_knowledge_law()
    mh, ml = T.extract_markers(kn_h, kn_l)
    print("markers health=%d law=%d" % (len(mh), len(ml)))
    for путь, марк in ((BZ, mh), (BP, ml)):
        pp = os.path.join(путь, "passport.json")
        ps = json.load(open(pp, encoding="utf-8"))
        ps["маркеры"] = марк
        json.dump(ps, open(pp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("updated", путь)


if __name__ == "__main__":
    main()
