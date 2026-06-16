from tools.import_recipes import build_payload


def test_build_payload_uses_parsed_ingredients_and_steps():
    recipe = {
        "title": "Тест",
        "description": "Вступление.",
        "ingredients": "картофель, соль",
        "ingredients_parsed": [
            {"name": "Картофель", "amount": "5", "unit": "шт."},
            {"name": "Соль", "amount": "по вкусу", "unit": None},
        ],
        "steps": ["Почистить картошку.", "Посолить."],
        "image_url": "https://e/x.jpg",
    }
    p = build_payload(recipe)
    assert p["ingredients"] == [
        {"name": "Картофель", "amount": "5", "unit": "шт."},
        {"name": "Соль", "amount": "по вкусу", "unit": None},
    ]
    assert p["description"].startswith("Вступление.")
    assert "Приготовление:" in p["description"]
    assert "1. Почистить картошку." in p["description"]
    assert "2. Посолить." in p["description"]
    assert p["photo_url"] == "https://e/x.jpg"
    assert p["servings"] == 4


def test_build_payload_clamps_overlong_unit():
    # backend: Ingredient.unit String(30), amount String(50), name String(100).
    # Слишком длинный unit (как у «Ленивых суши») должен обрезаться, а не ронять импорт 500.
    recipe = {
        "title": "Длинные единицы",
        "description": "Опис.",
        "ingredients_parsed": [
            {"name": "Соль", "amount": "0,4", "unit": "ч. ложки с гор (+ к воде по вкусу)"},
        ],
        "image_url": None,
    }
    p = build_payload(recipe)
    unit = p["ingredients"][0]["unit"]
    assert len(unit) <= 30
    assert unit.startswith("ч. ложки")


def test_build_payload_fallback_without_enrichment():
    recipe = {
        "title": "Старый формат",
        "description": "Опис.",
        "ingredients": "картофель, сосиски...",
        "image_url": None,
    }
    p = build_payload(recipe)
    assert p["ingredients"] == [
        {"name": "картофель", "amount": "по вкусу", "unit": None},
        {"name": "сосиски", "amount": "по вкусу", "unit": None},
    ]
    assert p["description"] == "Опис."
    assert p["photo_url"] is None
