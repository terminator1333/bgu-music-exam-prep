#!/usr/bin/env python3
"""Extract the summary + glossary section from each lectures/lesson-*.md and
write it to app/summaries.json so the in-browser app can show lesson summaries.

The "summary section" is the hand-authored content that lives between the
count line and the first '## שאלות' heading in each lesson file.

Run: python3 scripts/extract_summaries.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LECTURES = ROOT / "lectures"
OUT = ROOT / "app" / "summaries.json"

QUESTIONS_HEADING_RE = re.compile(r"^## שאלות", re.MULTILINE)
TITLE_RE = re.compile(r"^# שיעור \d+ — (.*)$", re.MULTILINE)
SUMMARY_START_RE = re.compile(r"^## (?!שאלות)", re.MULTILINE)


def extract(md: str) -> dict[str, str]:
    title_match = TITLE_RE.search(md)
    title = title_match.group(1).strip() if title_match else ""
    questions_match = QUESTIONS_HEADING_RE.search(md)
    if not questions_match:
        return {"title": title, "markdown": ""}
    head = md[: questions_match.start()]
    summary_match = SUMMARY_START_RE.search(head)
    if not summary_match:
        return {"title": title, "markdown": ""}
    return {"title": title, "markdown": head[summary_match.start() :].rstrip() + "\n"}


def main():
    out: dict[str, dict[str, str]] = {}
    for f in sorted(LECTURES.glob("lesson-*.md")):
        m = re.search(r"lesson-(\d+)\.md$", f.name)
        if not m:
            continue
        lesson = m.group(1)
        out[lesson] = extract(f.read_text(encoding="utf-8"))
    OUT.write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {OUT} with {len(out)} lessons")


if __name__ == "__main__":
    main()
