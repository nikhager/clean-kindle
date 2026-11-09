"""Turn a Kindle "Export Notes" HTML file into Markdown bullets for Notion.

- Highlights become quoted bullets, cleaned of stray punctuation and
  footnote markers.
- Your own notes become unquoted sub-bullets under the highlight they belong to.
- The result is saved to your Desktop and, on a Mac, also copied to the
  clipboard so you can paste it straight into Notion.

Usage:
    python3 clean-kindle.py [export.html]
With no argument it uses the newest "*Notebook.html" in ~/Downloads.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

from bs4 import BeautifulSoup

# Footnote markers the book uses after words (Alamak*, giam siap§, ...)
FOOTNOTE_MARKS = "*†‡§‖¶"
# Punctuation left dangling at the edges when a highlight starts or stops mid-sentence
EDGE_JUNK_START = ",;:—–-…. "
EDGE_JUNK_END = ",;:—–- "


def fix_quotes(text):
	"""Pair up double quotes; drop the ones cut off by the highlight's edges.

	Paired quotes inside the highlight become single quotes so they don't clash
	with the double quotes added around the whole highlight. A pair wrapping the
	entire highlight is removed, since the outer quotes replace it.
	"""
	marks = []  # (index, is_opening)
	for i, c in enumerate(text):
		if c in "“„":
			marks.append((i, True))
		elif c == "”":
			marks.append((i, False))
		elif c == '"':
			before = text[i - 1] if i else " "
			marks.append((i, before in " (—["))

	stack, pairs, drop = [], {}, set()
	for i, opening in marks:
		if opening:
			stack.append(i)
		elif stack:
			pairs[stack.pop()] = i
		else:
			drop.add(i)
	drop.update(stack)

	if pairs.get(0) == len(text) - 1:
		drop.update((0, len(text) - 1))

	opens = set(pairs) - drop
	closes = set(pairs.values()) - drop
	return "".join(
		"" if i in drop else "‘" if i in opens else "’" if i in closes else c
		for i, c in enumerate(text)
	)


def clean_highlight(text):
	text = " ".join(text.split())

	# Footnote markers anywhere, plus letter footnotes after punctuation ("hoon.a")
	text = text.translate(str.maketrans("", "", FOOTNOTE_MARKS))
	text = re.sub(r"([.!?,’”\"])[a-z]$", r"\1", text)

	text = fix_quotes(text)

	# Dangling punctuation at the edges ("—Indonesia—", "school,")
	text = text.lstrip(EDGE_JUNK_START).rstrip(EDGE_JUNK_END)

	# Unmatched brackets from cutting a sentence ("Beverly Hills).")
	for open_, close in ("()", "[]"):
		if text.count(open_) != text.count(close):
			text = text.replace(open_, "").replace(close, "")

	return f'"{text.strip()}"'


def clean_note(text):
	return " ".join(text.split())


def parse_heading(text):
	"""'Highlight(yellow) - Genealogy > Page 18 · Location 113' -> (kind, chapter, location)."""
	text = " ".join(text.split())
	kind = "note" if text.startswith("Note") else "highlight"
	where = text.split(" - ", 1)[1] if " - " in text else ""
	chapter = where.split(" > ")[0] if " > " in where else None
	location = re.search(r"Location (\d+)", where)
	return kind, chapter, int(location.group(1)) if location else None


def to_markdown(html):
	soup = BeautifulSoup(html, features="html.parser")
	title = soup.select_one(".bookTitle").get_text(strip=True)
	author = soup.select_one(".authors").get_text(strip=True)
	lines = [f"# {title}", f"*{author}*", ""]

	chapter = None
	last_highlight_chapter = object()  # nothing yet
	for el in soup.select(".sectionHeading, .noteHeading"):
		if "sectionHeading" in el["class"]:
			lines += ["", f"## {el.get_text(strip=True)}"]
			chapter = None
			last_highlight_chapter = object()
			continue

		body = el.find_next_sibling(class_="noteText")
		if body is None:
			continue
		kind, this_chapter, _ = parse_heading(el.get_text(" "))

		if this_chapter and this_chapter != chapter:
			chapter = this_chapter
			lines += ["", f"### {chapter}"]

		if kind == "highlight":
			lines.append(f"- {clean_highlight(body.get_text())}")
			last_highlight_chapter = this_chapter
		elif last_highlight_chapter == this_chapter:
			# Kindle lists a note right after the highlight it's attached to
			lines.append(f"    - {clean_note(body.get_text())}")
		else:
			lines.append(f"- {clean_note(body.get_text())}")

	return "\n".join(lines).strip() + "\n"


def find_input():
	if len(sys.argv) > 1:
		return Path(sys.argv[1]).expanduser()
	exports = sorted(Path.home().glob("Downloads/*Notebook.html"), key=lambda p: p.stat().st_mtime)
	if exports:
		print(f"Using newest export: {exports[-1].name}")
		return exports[-1]
	return Path(input("file: ").strip().strip("'\"")).expanduser()


def main():
	src = find_input()
	markdown = to_markdown(src.read_text(encoding="utf-8"))

	out = Path.home() / "Desktop" / "clean-highlights.md"
	out.write_text(markdown, encoding="utf-8")

	if shutil.which("pbcopy"):
		subprocess.run(["pbcopy"], input=markdown, text=True, check=True)
		print(f"Copied to clipboard and saved to {out}")
	else:
		print(f"Saved to {out}")


if __name__ == "__main__":
	main()
