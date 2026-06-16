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


def fetch_html(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (recipe importer)"}
    with httpx.Client(timeout=15, follow_redirects=True, headers=headers) as client:
        resp = client.get(url)
    resp.raise_for_status()
    return resp.text


def enrich(recipes: list[dict], limit: int | None = None) -> list[dict]:
    todo = recipes[:limit] if limit else recipes
    for r in todo:
        url = r.get("url")
        if not url:
            r["ingredients_parsed"], r["steps"] = [], []
            continue
        try:
            html = fetch_html(url)
            r["ingredients_parsed"] = parse_ingredients(html)
            r["steps"] = parse_steps(html)
            print(f"OK: {r['title']} — {len(r['ingredients_parsed'])} ингр., {len(r['steps'])} шагов")
        except Exception as exc:  # noqa: BLE001 — одна страница не должна валить прогон
            r["ingredients_parsed"], r["steps"] = [], []
            print(f"WARN: {r['title']} — не распарсено: {exc}")
        time.sleep(1)  # вежливость к серверу
    return todo


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument("--output", default=str(DEFAULT_OUTPUT))
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    recipes = json.loads(Path(args.input).read_text(encoding="utf-8"))
    enriched = enrich(recipes, args.limit)
    Path(args.output).write_text(
        json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nЗаписано {len(enriched)} рецептов в {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
