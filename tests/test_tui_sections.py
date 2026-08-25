"""Unit tests for the TUI section model (pure logic, no UI)."""

from writing_assistant.tui.sections import (
    Section,
    SectionState,
    parse_sections,
    replace_section_text,
    restore_saved_sections,
    section_index_at,
    text_similarity,
)


def test_parse_sections_splits_on_blank_lines_and_tracks_offsets():
    text = "First para.\n\nSecond para\nstill second.\n\n\nThird."
    sections = parse_sections(text)
    assert [s.text for s in sections] == [
        "First para.",
        "Second para\nstill second.",
        "Third.",
    ]
    for section in sections:
        assert text[section.start : section.end].strip() == section.text


def test_parse_sections_empty_text():
    assert parse_sections("") == []
    assert parse_sections("  \n\n  ") == []


def test_parse_sections_keeps_suggestion_for_similar_text():
    old = parse_sections("Hello world this is a paragraph.\n\nAnother one.")
    old[0].generated_text = "A suggestion"
    new = parse_sections("Hello world this is a paragraph!\n\nAnother one.", old)
    assert new[0].generated_text == "A suggestion"
    assert new[0].original_text == "Hello world this is a paragraph."
    assert new[1].generated_text == ""


def test_parse_sections_drops_suggestion_when_text_changes_completely():
    old = parse_sections("Hello world this is a paragraph.")
    old[0].generated_text = "A suggestion"
    new = parse_sections("Completely different content entirely.", old)
    assert new[0].generated_text == ""


def test_parse_sections_follows_moved_section():
    old = parse_sections("Alpha paragraph text here.\n\nSomething else entirely.")
    old[1].generated_text = "beta suggestion"
    new = parse_sections(
        "Inserted new paragraph.\n\nAlpha paragraph text here.\n\n"
        "Something else entirely.",
        old,
    )
    assert [s.generated_text for s in new] == ["", "", "beta suggestion"]


def test_section_index_at_boundaries():
    sections = parse_sections("aaa\n\nbbb")
    assert section_index_at(sections, 0) == 0
    assert section_index_at(sections, 3) == 0
    assert section_index_at(sections, 4) == -1
    assert section_index_at(sections, 5) == 1
    assert section_index_at(sections, 8) == 1
    assert section_index_at([], 0) == -1


def test_text_similarity():
    assert text_similarity("", "") == 0.0
    assert text_similarity("abc", "abc") == 1.0
    assert text_similarity("Abc", "abc ") == 1.0
    assert text_similarity("a", "abcdefghij") == 0.1
    assert 0.5 < text_similarity("hello world", "hello there") < 1.0


def test_context_around_collects_neighbours():
    sections = parse_sections("one\n\ntwo\n\nthree\n\nfour")
    state = SectionState(sections, 2)
    prev, nxt = state.context_around(2)
    assert prev == "one\n\ntwo"
    assert nxt == "four"
    assert state.current is sections[2]
    assert SectionState(sections, -1).current is None


def test_context_around_stops_at_limit():
    big = "x" * 2500
    sections = parse_sections(f"far\n\n{big}\n\nsmall\n\ncurrent")
    prev, _ = SectionState(sections, 3).context_around(3)
    # Like the web editor: whole sections are added until the limit is
    # reached (the server trims the excess), so "far" is never collected.
    assert prev == f"{big}\n\nsmall"


def test_restore_saved_sections_uses_similarity():
    sections = parse_sections("Hello there world.\n\nSecond section.")
    restore_saved_sections(
        sections,
        [
            {"text": "Hello there world!", "generated_text": "kept"},
            {"text": "Totally unrelated words.", "generated_text": "dropped"},
        ],
    )
    assert sections[0].generated_text == "kept"
    assert sections[1].generated_text == ""
    restore_saved_sections(sections, None)  # no-op


def test_replace_section_text_and_document_dict():
    text = "aaa\n\nbbb\n\nccc"
    sections = parse_sections(text)
    assert replace_section_text(text, sections[1], "BBB") == "aaa\n\nBBB\n\nccc"
    as_dict = Section("section-0", "aaa", 0, 3, "sugg").to_document_dict()
    assert as_dict == {
        "id": "section-0",
        "text": "aaa",
        "startPos": 0,
        "endPos": 3,
        "generated_text": "sugg",
    }
