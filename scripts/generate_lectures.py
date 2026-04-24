#!/usr/bin/env python3
"""Render one Markdown file per lesson under lectures/, with each question's
correct option bolded and its explanation underneath.

Reads app/questions.json. Bank questions come first; slide-derived questions
appear in a separate section at the bottom of each file.

Run: python3 scripts/generate_lectures.py
"""
from __future__ import annotations

import json
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


def render_lesson(lesson: int, title: str, items: list[dict]) -> str:
    bank = [q for q in items if q["source"] == "bank"]
    slides = [q for q in items if q["source"] == "slides"]
    parts = [f"# שיעור {lesson} — {title}", ""]
    parts.append(f"{len(bank)} שאלות מהשאלון הרשמי · {len(slides)} שאלות נגזרות מהמצגת.")
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


def main():
    data = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    by_lesson: dict[int, list[dict]] = defaultdict(list)
    titles: dict[int, str] = {}
    for q in data:
        by_lesson[q["lesson"]].append(q)
        titles[q["lesson"]] = q.get("lesson_title", "")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for lesson in sorted(by_lesson):
        md = render_lesson(lesson, titles[lesson], by_lesson[lesson])
        path = OUT_DIR / f"lesson-{lesson}.md"
        path.write_text(md, encoding="utf-8")
        print(f"Wrote {path} ({len(by_lesson[lesson])} questions)")


if __name__ == "__main__":
    main()
