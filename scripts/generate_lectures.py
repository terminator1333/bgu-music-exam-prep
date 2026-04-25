#!/usr/bin/env python3
"""Render one Markdown file per lesson under lectures/, with each question's
correct option bolded and its explanation underneath.

Reads app/questions.json. Bank questions come first; slide-derived questions
appear in a separate section at the bottom of each file.

Hand-authored summary/glossary sections that sit between the count line and
the first "## שאלות" heading are preserved on regeneration.

Run: python3 scripts/generate_lectures.py
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_PATH = ROOT / "app" / "questions.json"
OUT_DIR = ROOT / "lectures"

HEB_LETTERS = ["א", "ב", "ג", "ד"]


def render_question(q: dict) -> str:
    lines = [f"### {q['id']} — {q['question']}"]
    for i, opt in enumerate(q["options"]):
        letter = HEB_LETTERS[i]
        if i == q["correct"]:
            lines.append(f"- **{letter}. {opt}** ✅")
        else:
            lines.append(f"- {letter}. {opt}")
    if q.get("explanation"):
        lines.append("")
        lines.append(f"> {q['explanation']}")
    return "\n".join(lines)


def render_lesson(lesson: int, title: str, items: list[dict], summary_block: str = "") -> str:
    bank = [q for q in items if q["source"] == "bank"]
    slides = [q for q in items if q["source"] == "slides"]
    parts = [f"# שיעור {lesson} — {title}", ""]
    parts.append(f"{len(bank)} שאלות מהשאלון הרשמי · {len(slides)} שאלות נגזרות מהמצגת.")
    parts.append("")
    if summary_block:
        parts.append(summary_block.rstrip())
        parts.append("")
    if bank:
        parts.append("## שאלות מהשאלון (שאלון)")
        parts.append("")
        for q in bank:
            parts.append(render_question(q))
            parts.append("")
    if slides:
        parts.append("## שאלות מהמצגת (מצגת)")
        parts.append("")
        for q in slides:
            parts.append(render_question(q))
            parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def extract_summary_block(md: str) -> str:
    """Return content between the count line and the first '## שאלות' heading.

    This is the hand-authored summary/glossary section. Returns an empty
    string if the file doesn't have one yet.
    """
    questions_match = re.search(r"^## שאלות", md, re.MULTILINE)
    if not questions_match:
        return ""
    head = md[: questions_match.start()]
    # Skip the title (first '#' heading) and the count line that follows it.
    summary_match = re.search(r"^## (?!שאלות)", head, re.MULTILINE)
    if not summary_match:
        return ""
    return head[summary_match.start() :].rstrip()


def main():
    data = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    by_lesson: dict[int, list[dict]] = defaultdict(list)
    titles: dict[int, str] = {}
    for q in data:
        by_lesson[q["lesson"]].append(q)
        titles[q["lesson"]] = q.get("lesson_title", "")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for lesson in sorted(by_lesson):
        path = OUT_DIR / f"lesson-{lesson}.md"
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        summary_block = extract_summary_block(existing)
        md = render_lesson(lesson, titles[lesson], by_lesson[lesson], summary_block)
        path.write_text(md, encoding="utf-8")
        kept = " (kept summary)" if summary_block else ""
        print(f"Wrote {path} ({len(by_lesson[lesson])} questions){kept}")


if __name__ == "__main__":
    main()
