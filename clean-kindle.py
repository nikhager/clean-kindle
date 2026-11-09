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
SENTENCE_ENDERS = ".?!"
OPENERS = "([{"
CLOSERS = ")]}"


def quote_marks(text):
	"""Find quote marks as (index, kind, is_opening). kind is 'double' or 'single'.

	A ’ only counts as a closing single quote when a ‘ is open and the ’ isn't
	inside a word, so apostrophes (he’s, Joneses’ house) are left alone.
	"""
	marks, singles_open = [], 0
	for i, c in enumerate(text):
		before = text[i - 1] if i else " "
		after = text[i + 1] if i + 1 < len(text) else " "
		if c in "“„":
			marks.append((i, "double", True))
		elif c == "”":
			marks.append((i, "double", False))
		elif c == '"':
			marks.append((i, "double", not before.isalnum() and before not in SENTENCE_ENDERS + ",;:"))
		elif c == "‘":
			marks.append((i, "single", True))
			singles_open += 1
		elif c == "’" and singles_open and not after.isalpha():
			marks.append((i, "single", False))
			singles_open -= 1
	return marks


def fix_pairs(text):
	"""Drop quote marks and brackets that lost their partner.

	Highlights start and stop mid-sentence, so they often keep one half of a
	pair ("Alamak,  or  Beverly Hills).). Matched quotes are restyled for
	nesting inside the outer quotes added around the whole highlight: first
	level single, second level double, and so on.
	"""
	marks = [(i, kind, opening) for i, kind, opening in quote_marks(text)]
	marks += [(i, c, True) for i, c in enumerate(text) if c in OPENERS]
	marks += [(i, OPENERS[CLOSERS.index(c)], False) for i, c in enumerate(text) if c in CLOSERS]
	marks.sort()

	stack, pairs, drop = [], [], set()
	for i, kind, opening in marks:
		if opening:
			stack.append((i, kind))
		elif stack and stack[-1][1] == kind:
			pairs.append((stack.pop()[0], i, kind))
		elif any(k == kind for _, k in stack):
			# Close the matching opener; anything opened inside it was cut off
			while stack[-1][1] != kind:
				drop.add(stack.pop()[0])
			pairs.append((stack.pop()[0], i, kind))
		else:
			drop.add(i)
	drop.update(i for i, _ in stack)

	# A quote wrapping the whole highlight is replaced by the outer quotes
	for open_, close, kind in pairs:
		if kind in ("double", "single") and open_ == 0 and close == len(text) - 1:
			drop.update((open_, close))

	replace = {i: "" for i in drop}
	quote_pairs = sorted((o, c) for o, c, k in pairs if k in ("double", "single") and o not in drop)
	for open_, close in quote_pairs:
		depth = sum(1 for o, c in quote_pairs if o < open_ and close < c)
		replace[open_], replace[close] = ("‘", "’") if depth % 2 == 0 else ("“", "”")

	return "".join(replace.get(i, c) for i, c in enumerate(text))


def clean_highlight(text):
	text = " ".join(text.split())

	# Footnote markers anywhere, plus letter footnotes after punctuation ("hoon.a")
	text = text.translate(str.maketrans("", "", FOOTNOTE_MARKS))
	text = re.sub(r"([.!?,’”\"])[a-z]$", r"\1", text)

	text = fix_pairs(text).strip()

	# Every pair left is complete, so the only things allowed at the edges are
	# letters/digits, sentence enders at the end, and the halves of real pairs.
	ok_start = set(OPENERS + "‘“")
	ok_end = set(SENTENCE_ENDERS + CLOSERS + "’”")
	while text and not (text[0].isalnum() or text[0] in ok_start):
		text = text[1:].lstrip()
	while text and not (text[-1].isalnum() or text[-1] in ok_end):
		text = text[:-1].rstrip()

	return f'"{text}"'


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
