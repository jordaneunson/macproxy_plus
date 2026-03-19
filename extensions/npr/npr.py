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

		return str(soup), response.status_code
	except Exception as e:
		return f"<html><body><b>Error:</b> {str(e)}</body></html>", 500

def handle_request(req):
	if req.host == "text.npr.org":
		return redirect(f"http://npr.org{req.path}")
	else:
		return handle_get(req)
