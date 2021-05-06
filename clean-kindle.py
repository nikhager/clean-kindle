import re
from bs4 import BeautifulSoup

def RemoveHighlights(soup):
	for tag in soup.find_all("h3", {'class':'noteHeading'}):
		tag.decompose()

def NotesToBullets(soup):
	for tag in soup.find_all("div", {'class':'noteText'}):
		tag.name = 'ul'

def main():
	file = input('file: ')
	clean = "/Users/nik/Desktop/clean-highlights.html"

	with open(file) as inf:
		txt = inf.read()
		soup = BeautifulSoup(txt, features='html.parser')
		RemoveHighlights(soup)
		NotesToBullets(soup)

	with open(clean, "w") as outf:
		outf.write(re.sub(r'\s([?.,!"](?:\s|$))', r'\1', str(soup.prettify())))

	print("Done")


if __name__ == '__main__':
	main()
