from pathlib import Path

from tools.scrape_russianfood import parse_ingredients, parse_steps

FIXTURE = (Path(__file__).parent / "fixtures" / "recipe_165007.html").read_text(encoding="utf-8")


def _by_name(items, name):
    return next(i for i in items if i["name"] == name)


def test_parse_ingredients_shtuki():
    items = parse_ingredients(FIXTURE)
    assert _by_name(items, "Картофель (некрупный)") == {
        "name": "Картофель (некрупный)", "amount": "5", "unit": "шт."
    }
    assert _by_name(items, "Сосиски") == {"name": "Сосиски", "amount": "4", "unit": "шт."}


def test_parse_ingredients_grams_and_spoons():
    items = parse_ingredients(FIXTURE)
    assert _by_name(items, "Сыр твёрдый") == {"name": "Сыр твёрдый", "amount": "90", "unit": "г"}
    assert _by_name(items, "Чеснок") == {"name": "Чеснок", "amount": "1", "unit": "зубчик"}
    assert _by_name(items, "Паприка молотая") == {
        "name": "Паприка молотая", "amount": "0,5", "unit": "ч. ложки"
    }


def test_parse_ingredients_non_numeric():
    items = parse_ingredients(FIXTURE)
    assert _by_name(items, "Перец чёрный молотый") == {
        "name": "Перец чёрный молотый", "amount": "щепотка (по вкусу)", "unit": None
    }


def test_parse_ingredients_skips_separator():
    items = parse_ingredients(FIXTURE)
    assert all(i["name"] != "*" for i in items)
    # вспомогательные (после *) тоже попадают
    assert any(i["name"].startswith("Масло подсолнечное") for i in items)
