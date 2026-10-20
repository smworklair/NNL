# -*- coding: utf-8 -*-
"""Ядро NNL как функция Vercel: тот же обработчик, что и в локальном сервере.py, без отдельного сервера."""
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qsl, urlencode, urlsplit

КОРЕНЬ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core")
sys.path.insert(0, os.path.join(КОРЕНЬ, "NNL", "диалог"))
import сервер as S  # noqa: E402

S.СИСТЕМА = S.Д.Система()


class handler(S.Обработчик, BaseHTTPRequestHandler):
    def parse_request(self):
        ок = super().parse_request()
        # Vercel при перезаписи /api/:path* в /api/index может передать хвост параметром path: возвращаем настоящий путь
        р = urlsplit(self.path)
        if ок and р.path.rstrip("/") == "/api/index":
            q = parse_qsl(р.query, keep_blank_values=True)
            хвост = next((з for к, з in q if к == "path"), "")
            остальное = [(к, з) for к, з in q if к != "path"]
            self.path = "/api/" + хвост + (("?" + urlencode(остальное)) if остальное else "")
        return ок
