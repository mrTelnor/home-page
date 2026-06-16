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


def test_parse_ingredients_en_dash_separator():
    # russianfood на части страниц использует длинное тире «–» вместо дефиса «-»
    html = (
        '<table><tr class="ingr_tr_0"><td><span>Крупа гречневая – 150 г</span></td></tr>'
        '<tr class="ingr_tr_1"><td><span>Морковь – 100 г (1 шт.)</span></td></tr>'
        '<tr class="ingr_tr_0"><td><span>Соль – по вкусу</span></td></tr></table>'
    )
    items = parse_ingredients(html)
    assert {"name": "Крупа гречневая", "amount": "150", "unit": "г"} in items
    assert {"name": "Морковь", "amount": "1", "unit": "шт."} in items
    assert {"name": "Соль", "amount": "по вкусу", "unit": None} in items


def test_parse_steps_basic():
    steps = parse_steps(FIXTURE)
    assert len(steps) >= 10
    assert steps[0].startswith("Подготовьте необходимые ингредиенты")
    # подписи-картинки не попадают в текст шагов
    assert all("Фото приготовления рецепта" not in s for s in steps)
    assert any("духовку" in s for s in steps)
