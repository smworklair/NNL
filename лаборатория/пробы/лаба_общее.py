# -*- coding: utf-8 -*-
"""Общие импорты и пути для лаб процессора v9.

Избавляет от дублирования sys.path.insert в каждой лабе.
"""
import os
import sys

КОРЕНЬ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.insert(0, os.path.join(КОРЕНЬ, "система", "замер"))
import общее as О  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
from процессор import Процессор  # noqa: E402
