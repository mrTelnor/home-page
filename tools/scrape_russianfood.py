"""Обогащение docs/рецепты.json данными со страниц russianfood:
структурированные ингредиенты (с количествами) и пошаговый рецепт.

Usage:
  python tools/scrape_russianfood.py [--limit N] [--input docs/рецепты.json] [--output docs/рецепты_full.json]
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "docs" / "рецепты.json"
DEFAULT_OUTPUT = ROOT / "docs" / "рецепты_full.json"

_SHT_RE = re.compile(r"\((\d+)\s*шт\.?\)")
_LEAD_NUM_RE = re.compile(r"^(\d+(?:[.,]\d+)?)\s+(.+)$")


def parse_ingredients(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []
    for row in soup.select("tr.ingr_tr_0, tr.ingr_tr_1"):
        text = row.get_text(" ", strip=True)
        if " - " not in text:  # строка-разделитель "*" и прочее
            continue
        name, qty = text.split(" - ", 1)
        name, qty = name.strip(), qty.strip()
        sht = _SHT_RE.search(qty)
        if sht:
            items.append({"name": name, "amount": sht.group(1), "unit": "шт."})
            continue
        lead = _LEAD_NUM_RE.match(qty)
        if lead:
            items.append({"name": name, "amount": lead.group(1), "unit": lead.group(2).strip()})
            continue
        items.append({"name": name, "amount": qty, "unit": None})
    return items


def parse_steps(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    steps: list[str] = []
    for p in soup.select("div.step_n p"):
        text = p.get_text(" ", strip=True)
        if text:
            steps.append(text)
    return steps
