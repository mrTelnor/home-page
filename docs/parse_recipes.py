"""Parse recipes with explicit 'Ингредиенты:' blocks from FB2 book.

Output: recipes.json — array of {title, description, servings, ingredients[]}.
"""
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

FB2_NS = "{http://www.gribuser.ru/xml/fictionbook/2.0}"

# Common Russian cooking units
UNITS = [
    "ст. л.", "ст.л.", "ч. л.", "ч.л.",
    "кг", "г", "мл", "л",
    "шт.", "шт",
    "зубчик", "зубчика", "зубчиков",
    "горсть", "горстей",
    "щепотка", "щепотки",
    "кочан", "кочана",
    "пучок", "пучка", "пучков",
]


def strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def p_text(elem: ET.Element) -> str:
    return "".join(elem.itertext()).strip()


def first_p(elem: ET.Element) -> str:
    for p in elem.iter(f"{FB2_NS}p"):
        t = p_text(p)
        if t:
            return t
    return ""


def is_ingredient_header(text: str) -> bool:
    """Check if paragraph is an ingredient section header."""
    t = text.strip().lower().rstrip(":").strip()
    return (
        t.startswith("ингредиент")
        or t.startswith("для ")  # "ДЛЯ СОУСА:", "ДЛЯ ТЕСТА:"
        or t.startswith("начинк")
    )


_QTY_RE = re.compile(r"^[\d½¼¾⅓⅔\s,./–\-]+")


def _extract_amount_unit(qty_str: str) -> tuple[str, str | None]:
    """Split '200 г' → ('200', 'г'); '2 ст. л.' → ('2', 'ст. л.')."""
    qty_str = qty_str.strip()
    for unit in sorted(UNITS, key=len, reverse=True):
        pattern = rf"(?i)\s*{re.escape(unit)}\s*$"
        m = re.search(pattern, qty_str)
        if m:
            amount = qty_str[: m.start()].strip()
            if amount:
                return amount, unit
    return qty_str, None


def parse_ingredient(line: str) -> dict | None:
    """Parse ingredient line. Supports two formats:

    A) 'Название – количество единица' (trailing dash)
    B) '– количество единица название' (leading dash)
    """
    line = line.replace("—", "–").replace("\u2011", "-").strip()
    if not line:
        return None

    # Format B: leading dash
    if line.startswith("–"):
        rest = line[1:].strip()
        if not rest:
            return None

        # Try to match leading quantity: "1,2 кг говядины..." or "1 яйцо"
        m = _QTY_RE.match(rest)
        if m and m.group().strip():
            qty_part = m.group().strip()
            name_part = rest[m.end():].strip()

            # Check if unit is at start of name_part (followed by space or end)
            for unit in sorted(UNITS, key=len, reverse=True):
                if re.match(rf"(?i){re.escape(unit)}(?:\s|$)", name_part):
                    amount = qty_part
                    name = name_part[len(unit):].strip()
                    if name:
                        return {"name": name, "amount": amount, "unit": unit}

            # No unit found — qty is amount, rest is name
            if name_part:
                return {"name": name_part, "amount": qty_part, "unit": None}

        # No leading quantity — whole rest is name, "по вкусу"
        return {"name": rest, "amount": "по вкусу", "unit": None}

    # Format A: trailing dash
    if "–" in line:
        name, qty_str = line.rsplit("–", 1)
        name = name.strip()
        qty_str = qty_str.strip()
        if not name:
            return None
        if not qty_str:
            return {"name": name, "amount": "по вкусу", "unit": None}
        amount, unit = _extract_amount_unit(qty_str)
        return {"name": name, "amount": amount, "unit": unit}

    # No dash — just a name, no amount
    return {"name": line, "amount": "по вкусу", "unit": None}


def parse_recipe_section(section: ET.Element) -> dict | None:
    """Parse one recipe section. Returns None if no ingredients found."""
    title_elem = section.find(f"{FB2_NS}title")
    title = first_p(title_elem) if title_elem is not None else ""
    if not title:
        return None

    # Collect all <p> in order, skip title
    paragraphs = []
    for elem in section.iter():
        if strip_ns(elem.tag) == "title":
            continue
        if strip_ns(elem.tag) == "p":
            t = p_text(elem)
            if t:
                paragraphs.append(t)

    # Skip if title paragraph got included
    if paragraphs and paragraphs[0] == title:
        paragraphs = paragraphs[1:]

    # Find ingredient block: starts with first "Ингредиенты..." paragraph
    ing_start = None
    for i, p in enumerate(paragraphs):
        if p.strip().lower().startswith("ингредиент"):
            ing_start = i
            break

    if ing_start is None:
        return None  # No explicit ingredients — skip

    # Strategy: only accept lines with explicit dash separator as ingredients.
    # Lines without any dash (like "Соль") are added only if sandwiched between
    # dashed ingredients and look short.

    def is_dashed_ingredient(p: str) -> bool:
        if is_ingredient_header(p):
            return False
        # Leading dash: format "– 1 кг говядины"
        if p.startswith(("–", "—")):
            rest = p[1:].strip()
            if not rest or rest.endswith(";"):
                return False
            # Ingredients typically start with capital letter or digit.
            # Instruction bullets start with lowercase (verb/adverb).
            first = rest[0]
            return first.isupper() or first.isdigit()
        # Middle dash: format "Тыква – 200 г".
        # The part after the last dash should be short (quantity + unit).
        if " – " in p or " — " in p:
            tail = p.rsplit(" – ", 1)[-1] if " – " in p else p.rsplit(" — ", 1)[-1]
            return len(tail) < 30 and len(p) < 250
        return False

    # Scan forward from ingredient header. Stop when we see TWO consecutive
    # long non-ingredient paragraphs — that's instructions.
    scan_limit = min(len(paragraphs), ing_start + 80)
    last_ing_idx = ing_start
    long_streak = 0
    for i in range(ing_start + 1, scan_limit):
        p = paragraphs[i]
        if is_dashed_ingredient(p):
            last_ing_idx = i
            long_streak = 0
        elif is_ingredient_header(p):
            long_streak = 0
            continue
        elif len(p) > 80:
            long_streak += 1
            if long_streak >= 2 and last_ing_idx > ing_start:
                break
        else:
            long_streak = 0

    ingredients = []
    for i in range(ing_start + 1, last_ing_idx + 1):
        p = paragraphs[i]
        if is_ingredient_header(p):
            continue
        if is_dashed_ingredient(p):
            ing = parse_ingredient(p)
            if ing:
                ingredients.append(ing)

    if not ingredients:
        return None

    description = "\n\n".join(paragraphs[last_ing_idx + 1:])

    # Servings: try to find in description
    servings = 4
    m = re.search(r"(\d+)\s*порц", description.lower())
    if m:
        servings = int(m.group(1))

    return {
        "title": title,
        "description": description,
        "servings": servings,
        "ingredients": ingredients,
    }


def main(path: Path) -> None:
    tree = ET.parse(path)
    root = tree.getroot()
    body = root.find(f"{FB2_NS}body")

    # Find "Рецепты" top-level section
    recipes_section = None
    for section in body.findall(f"{FB2_NS}section"):
        title_elem = section.find(f"{FB2_NS}title")
        if title_elem is not None and first_p(title_elem) == "Рецепты":
            recipes_section = section
            break

    if recipes_section is None:
        print("[ERROR] 'Рецепты' section not found", file=sys.stderr)
        return

    results = []
    for sub in recipes_section.findall(f"{FB2_NS}section"):
        recipe = parse_recipe_section(sub)
        if recipe:
            results.append(recipe)
            print(f"[OK] {recipe['title']!r} — {len(recipe['ingredients'])} ingredients")

    output = Path(__file__).parent / "recipes.json"
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved {len(results)} recipes to {output}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
