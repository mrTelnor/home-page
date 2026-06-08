from migrate_obsidian.slugify import slugify


def test_basic():
    assert slugify("Hello World") == "hello-world"


def test_cyrillic():
    assert slugify("Электронный дневник") == "elektronnyi-dnevnik"


def test_strips_punctuation():
    assert slugify("Foo / Bar: baz?") == "foo-bar-baz"


def test_idempotent():
    assert slugify("Я с пробелом") == slugify("Я с пробелом")
