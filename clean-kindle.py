import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup

def RemoveHighlights(soup):
	for tag in soup.find_all("h3", {'class':'noteHeading'}):
		tag.decompose()

def NotesToBullets(soup):
	for tag in soup.find_all("div", {'class':'noteText'}):
		tag.name = 'ul'

def main():
	# Input file: first command-line argument, or ask for it
	file = sys.argv[1] if len(sys.argv) > 1 else input('file: ').strip().strip("'\"")
	# Output goes on the Desktop of whoever runs it
	clean = Path.home() / "Desktop" / "clean-highlights.html"

	with open(file) as inf:
		txt = inf.read()
		soup = BeautifulSoup(txt, features='html.parser')
		RemoveHighlights(soup)
		NotesToBullets(soup)

	with open(clean, "w") as outf:
		outf.write(re.sub(r'\s([?.,!"](?:\s|$))', r'\1', str(soup.prettify())))

	print(f"Done: {clean}")


if __name__ == '__main__':
	main()
