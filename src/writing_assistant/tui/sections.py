"""Section model shared by the TUI and the document format.

Mirrors the behaviour of the web editor (``static/script.js``): a document's
text is split into sections at blank lines, each section remembers the AI
suggestion generated for it, and suggestions survive edits as long as the
section text stays mostly the same. Kept free of any UI dependency so it can
be unit-tested directly.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

# The web client truncates surrounding context to this many characters and
# the server does the same; keep the TUI consistent.
CONTEXT_LIMIT = 2000

# Suggestions are kept across edits while at least this share of the section
# text is unchanged (same threshold as the web editor).
SIMILARITY_THRESHOLD = 0.5

_BLANK_LINE = re.compile(r"\n\s*\n")


@dataclass
class Section:
    """One paragraph of the document plus its AI suggestion, if any."""

    id: str
    text: str
    start: int
    end: int
    generated_text: str = ""
    original_text: str | None = None

    def to_document_dict(self) -> dict[str, Any]:
        """The JSON shape the web client stores in a saved document."""
        data = asdict(self)
        # Field names in the saved format follow the web client.
        data["startPos"] = data.pop("start")
        data["endPos"] = data.pop("end")
        if data["original_text"] is None:
            del data["original_text"]
        return data


@dataclass
class SectionState:
    """The parsed sections of a document and the one under the cursor."""

    sections: list[Section] = field(default_factory=list)
    current_index: int = -1

    @property
    def current(self) -> Section | None:
        if 0 <= self.current_index < len(self.sections):
            return self.sections[self.current_index]
        return None

    def context_around(self, index: int) -> tuple[str, str]:
        """Previous and next context for the section at ``index``.

        Collects whole neighbouring sections until ``CONTEXT_LIMIT``
        characters are gathered on each side; the server trims the excess.
        """
        prev_parts: list[str] = []
        prev_len = 0
        for i in range(index - 1, -1, -1):
            if prev_len >= CONTEXT_LIMIT:
                break
            prev_parts.insert(0, self.sections[i].text)
            prev_len += len(self.sections[i].text)
        next_parts: list[str] = []
        next_len = 0
        for i in range(index + 1, len(self.sections)):
            if next_len >= CONTEXT_LIMIT:
                break
            next_parts.append(self.sections[i].text)
            next_len += len(self.sections[i].text)
        return "\n\n".join(prev_parts), "\n\n".join(next_parts)


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb))
            )
        previous = current
    return previous[-1]


def text_similarity(a: str, b: str) -> float:
    """Similarity in [0, 1], matching the web editor's heuristic.

    Case-insensitive Levenshtein ratio, with the same cheap length pre-filter
    the JavaScript uses (a >2x length difference cannot pass the threshold).
    """
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    s1, s2 = a.strip().lower(), b.strip().lower()
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    shorter, longer = min(len(s1), len(s2)), max(len(s1), len(s2))
    if longer > 2 * shorter:
        return shorter / longer
    return 1 - _levenshtein(s1, s2) / longer


def parse_sections(text: str, previous: list[Section] | None = None) -> list[Section]:
    """Split ``text`` into sections at blank lines.

    Suggestions from ``previous`` are carried over to the new sections whose
    text still resembles the text the suggestion was generated for.
    """
    old = list(previous or [])
    matched: set[int] = set()
    sections: list[Section] = []
    if not text.strip():
        return sections

    position = 0
    for index, raw in enumerate(_BLANK_LINE.split(text)):
        stripped = raw.strip()
        if not stripped:
            continue
        start = text.index(raw, position)
        end = start + len(raw)
        position = end
        section = Section(id=f"section-{index}", text=stripped, start=start, end=end)

        match = -1
        if (
            index < len(old)
            and index not in matched
            and old[index].generated_text
            and text_similarity(old[index].original_text or old[index].text, stripped)
            > SIMILARITY_THRESHOLD
        ):
            match = index
        if match == -1:
            for old_index, candidate in enumerate(old):
                if old_index == index or old_index in matched:
                    continue
                if not candidate.generated_text:
                    continue
                if (
                    text_similarity(candidate.original_text or candidate.text, stripped)
                    > SIMILARITY_THRESHOLD
                ):
                    match = old_index
                    break
        if match != -1:
            section.generated_text = old[match].generated_text
            section.original_text = old[match].original_text or old[match].text
            matched.add(match)
        sections.append(section)
    return sections


def section_index_at(sections: list[Section], cursor: int) -> int:
    """Index of the section containing character offset ``cursor``, or -1."""
    for i, section in enumerate(sections):
        if section.start <= cursor <= section.end:
            return i
    return -1


def restore_saved_sections(
    sections: list[Section], saved: list[dict[str, Any]] | None
) -> None:
    """Re-attach suggestions stored in a saved document to parsed sections."""
    if not saved:
        return
    for section, saved_section in zip(sections, saved, strict=False):
        generated = saved_section.get("generated_text") or ""
        if not generated:
            continue
        if (
            text_similarity(section.text, saved_section.get("text") or "")
            > SIMILARITY_THRESHOLD
        ):
            section.generated_text = generated


def replace_section_text(text: str, section: Section, new_text: str) -> str:
    """Return ``text`` with ``section``'s span replaced by ``new_text``."""
    return text[: section.start] + new_text + text[section.end :]
