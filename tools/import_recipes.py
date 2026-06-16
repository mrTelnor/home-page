"""Импорт рецептов из docs/рецепты.json в API home-page как админ.

Usage:
  python tools/import_recipes.py --base-url https://api.telnor.ru \
      --username admin --password '...' [--limit N] [--dry-run]
"""
import argparse
import json
import sys
from pathlib import Path

import httpx

JSON_PATH = Path(__file__).resolve().parents[1] / "docs" / "рецепты_full.json"


def parse_ingredients(raw: str) -> list[dict]:
    items = []
    for part in (raw or "").split(","):
        name = part.strip().strip(".").strip()
        if name:
            items.append({"name": name, "amount": "по вкусу", "unit": None})
    return items


def build_payload(recipe: dict) -> dict:
    parsed = recipe.get("ingredients_parsed")
    if parsed:
        ingredients = [
            {"name": i["name"], "amount": i["amount"], "unit": i.get("unit")}
            for i in parsed
        ]
    else:
        ingredients = parse_ingredients(recipe.get("ingredients", ""))

    description = (recipe.get("description") or "").strip()
    steps = recipe.get("steps") or []
    if steps:
        numbered = "\n".join(f"{n}. {s}" for n, s in enumerate(steps, 1))
        description = (description + "\n\nПриготовление:\n" + numbered).strip()

    return {
        "title": recipe["title"],
        "description": description or None,
        "servings": 4,
        "ingredients": ingredients,
        "photo_url": recipe.get("image_url") or None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--username", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    recipes = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    if args.limit:
        recipes = recipes[: args.limit]

    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        login = client.post(
            "/api/auth/login",
            json={"username": args.username, "password": args.password},
        )
        login.raise_for_status()  # cookie сохраняется в client

        existing = {r["title"] for r in client.get("/api/recipes").json()}

        added = skipped = no_photo = 0
        for r in recipes:
            title = r["title"]
            if title in existing:
                print(f"SKIP (дубль): {title}")
                skipped += 1
                continue
            payload = build_payload(r)
            if args.dry_run:
                photo = "да" if payload["photo_url"] else "нет"
                print(f"DRY: {title} ({len(payload['ingredients'])} ингр., photo={photo})")
                continue
            resp = client.post("/api/recipes", json=payload)
            if resp.status_code != 201:
                print(f"FAIL {resp.status_code}: {title} — {resp.text[:200]}")
                continue
            body = resp.json()
            existing.add(title)
            added += 1
            if payload["photo_url"] and not body.get("image_url"):
                no_photo += 1
                print(f"OK (без фото!): {title}")
            else:
                print(f"OK: {title}")
        print(f"\nИтого: добавлено {added}, пропущено {skipped}, без фото {no_photo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
