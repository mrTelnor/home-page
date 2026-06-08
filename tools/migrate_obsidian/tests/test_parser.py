from pathlib import Path

from migrate_obsidian.parser import parse_note

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_simple():
    p = parse_note(FIXTURES / "simple.md")
    assert p.title == "simple"
    assert "Тело заметки" in p.content
    assert p.tags == []
    assert p.links == []
    assert p.metadata == {}


def test_parse_frontmatter():
    p = parse_note(FIXTURES / "with_frontmatter.md")
    assert p.metadata["custom_field"] == 42
    assert "project" in p.tags
    assert "idea" in p.tags


def test_parse_inline_links_and_tags():
    p = parse_note(FIXTURES / "with_links_and_tags.md")
    targets = {(l.target, l.alias) for l in p.links}
    assert ("Other Note", None) in targets
    assert ("Third Note", "алиас") in targets
    assert "work" in p.tags
    assert "idea" in p.tags
