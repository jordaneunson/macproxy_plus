from flask import request, redirect
import requests
from bs4 import BeautifulSoup

DOMAIN = "npr.org"

def handle_get(req):
	url = f"https://text.npr.org{req.path}"
	try:
		response = requests.get(url)

		soup = BeautifulSoup(response.text, 'html.parser')

		# Remove header tag
		header_tag = soup.find('header')
		if header_tag:
			header_tag.decompose()

		# Remove style tags and link stylesheets (MacWeb can't use them)
		for tag in soup.find_all(['style', 'link', 'script']):
			tag.decompose()

		# Remove inline styles
		for tag in soup.find_all(True):
			if tag.has_attr('style'):
				del tag['style']
			if tag.has_attr('class'):
				del tag['class']

		# Modify relative URLs to absolute URLs pointing back through proxy
		for tag in soup.find_all(['a', 'img']):
			if tag.has_attr('href'):
				href = tag['href']
				if href.startswith('/'):
					tag['href'] = f"http://npr.org{href}"
				elif href.startswith('https://'):
					tag['href'] = href.replace('https://', 'http://')
			if tag.has_attr('src'):
				src = tag['src']
				if src.startswith('/'):
					tag['src'] = f"http://npr.org{src}"

		updated_html = str(soup)

		# ASCII substitution for classic Mac browsers
		char_map = {
			'\u2018': "'", '\u2019': "'", '\u201C': '"', '\u201D': '"',
			'\u2013': '-', '\u2014': '--', '\u2026': '...', '\u00A0': ' ',
			'\u2032': "'", '\u2033': '"', '\u00AB': '<<', '\u00BB': '>>',
			'\u2022': '*', '\u00B7': '*', '\u2010': '-', '\u2011': '-',
			'\u2012': '-', '\u2015': '--', '\u2212': '-', '\u00D7': 'x',
			'\u00F7': '/', '\u2190': '<-', '\u2192': '->', '\u2264': '<=',
			'\u2265': '>=', '\u00A9': '(c)', '\u00AE': '(R)', '\u2122': '(TM)',
			'\u00BC': '1/4', '\u00BD': '1/2', '\u00BE': '3/4', '\u00B0': ' deg',
		}
		for char, replacement in char_map.items():
			updated_html = updated_html.replace(char, replacement)
		cleaned = []
		for ch in updated_html:
			if ord(ch) < 128:
				cleaned.append(ch)
			else:
				cleaned.append('?')
		return ''.join(cleaned), response.status_code
	except Exception as e:
		return f"<html><body><b>Error:</b> {str(e)}</body></html>", 500

def handle_request(req):
	if req.host == "text.npr.org":
		return redirect(f"http://npr.org{req.path}")
	else:
		return handle_get(req)
