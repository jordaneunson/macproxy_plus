import requests
from bs4 import BeautifulSoup
from flask import Response
import io
from PIL import Image
import base64
import hashlib
import os
import shutil
import mimetypes

DOMAIN = "reddit.com"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"

def handle_request(request):
	if request.method != 'GET':
		return Response("Only GET requests are supported", status=405)

	url = request.url

	# Outbound proxy — fetch external article, strip images/CSS/JS
	if '/outbound' in request.path:
		target = request.args.get('url', '')
		if not target:
			return Response("No URL specified", status=400)
		return handle_outbound(target)

	if not url.startswith(('http://old.reddit.com', 'https://old.reddit.com')):
		url = url.replace("reddit.com", "old.reddit.com", 1)
	
	try:
		headers = {'User-Agent': USER_AGENT} if USER_AGENT else {}
		resp = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
		resp.raise_for_status()
		return process_content(resp.content, url)
	except requests.RequestException as e:
		return Response(f"An error occurred: {str(e)}", status=500)


def handle_outbound(target_url):
	"""Fetch an external page linked from Reddit, strip images and heavy content."""
	import urllib.parse

	# ASCII substitution map (same as process_content)
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

	try:
		headers = {'User-Agent': USER_AGENT}
		resp = requests.get(target_url, headers=headers, allow_redirects=True, timeout=15)
		resp.raise_for_status()
	except requests.RequestException as e:
		return f"<html><head><title>Error</title></head><body><p><b>Could not load article:</b> {str(e)}</p><p><a href=\"http://reddit.com/\">Back to Reddit</a></p></body></html>", 500

	soup = BeautifulSoup(resp.content, 'html.parser')

	# Extract page title
	page_title = soup.title.string.strip() if soup.title and soup.title.string else target_url

	# Remove all images, scripts, styles, iframes, video, audio, svg, canvas, noscript
	for tag in soup.find_all(['img', 'script', 'style', 'iframe', 'video', 'audio',
							  'svg', 'canvas', 'noscript', 'picture', 'source', 'figure']):
		tag.decompose()

	# Remove all style attributes
	for tag in soup.find_all(True):
		if tag.has_attr('style'):
			del tag['style']
		if tag.has_attr('class'):
			del tag['class']

	# Try to find the article body
	article = (
		soup.find('article') or
		soup.find('div', {'role': 'article'}) or
		soup.find('div', id=lambda x: x and 'article' in x.lower()) or
		soup.find('main') or
		soup.find('div', id='content') or
		soup.find('div', class_='content')
	)

	if article:
		body_text = article.get_text(separator='\n', strip=True)
	else:
		# Fallback: grab the whole body
		body_tag = soup.find('body')
		body_text = body_tag.get_text(separator='\n', strip=True) if body_tag else ''

	# Clean up excessive blank lines
	lines = [line.strip() for line in body_text.split('\n')]
	lines = [line for line in lines if line]
	# Truncate very long articles
	if len(lines) > 200:
		lines = lines[:200]
		lines.append('[Article truncated]')

	body_html = '\n'.join(f'<p>{line}</p>' for line in lines)

	html = (
		f'<html><head><title>{page_title}</title></head><body>'
		f'<h2>{page_title}</h2>'
		f'<font size="2"><a href="{target_url}">{target_url}</a></font>'
		f'<hr>'
		f'{body_html}'
		f'<hr>'
		f'<a href="http://reddit.com/">Back to Reddit</a>'
		f'</body></html>'
	)

	# ASCII cleanup
	for char, replacement in char_map.items():
		html = html.replace(char, replacement)
	cleaned = []
	for ch in html:
		if ord(ch) < 128:
			cleaned.append(ch)
		else:
			cleaned.append('?')
	return ''.join(cleaned), 200

def process_comments(comments_area, parent_element, new_soup, depth=0, max_top=None, max_depth=None):
	count = 0
	for comment in comments_area.find_all('div', class_='thing', recursive=False):
		if 'comment' not in comment.get('class', []):
			continue  # Skip if it's not a comment
		if max_top is not None and depth == 0 and count >= max_top:
			more_p = new_soup.new_tag('p')
			more_p.string = f"[{len(comments_area.find_all('div', class_='thing', recursive=False)) - max_top} more comments not shown]"
			parent_element.append(more_p)
			break
		if max_depth is not None and depth >= max_depth:
			return
		count += 1

		comment_div = new_soup.new_tag('div')
		if depth > 0:
			blockquote = new_soup.new_tag('blockquote')
			parent_element.append(blockquote)
			blockquote.append(comment_div)
		else:
			parent_element.append(comment_div)

		# Author, points, and time
		author_element = comment.find('a', class_='author')
		author = author_element.string if author_element else 'Unknown'
		
		score_element = comment.find('span', class_='score unvoted')
		points = score_element.string.split()[0] if score_element else '0'
		
		time_element = comment.find('time', class_='live-timestamp')
		time_passed = time_element.string if time_element else 'Unknown time'
		
		header = new_soup.new_tag('p')
		author_b = new_soup.new_tag('b')
		author_b.string = author
		header.append(author_b)
		header.append(f" | {points} points | {time_passed}")
		comment_div.append(header)

		# Comment body
		comment_body = comment.find('div', class_='md')
		if comment_body:
			body_text = comment_body.get_text().strip()
			if body_text:
				body_p = new_soup.new_tag('p')
				body_p.string = body_text
				comment_div.append(body_p)

		# Extra space between comments
		comment_div.append(new_soup.new_tag('br'))

		# Process child comments
		child_area = comment.find('div', class_='child')
		if child_area:
			child_comments = child_area.find('div', class_='sitetable listing')
			if child_comments:
				process_comments(child_comments, comment_div, new_soup, depth + 1, max_top=max_top, max_depth=max_depth)

def process_content(content, url):
	soup = BeautifulSoup(content, 'html.parser')
	
	new_soup = BeautifulSoup('', 'html.parser')
	html = new_soup.new_tag('html')
	new_soup.append(html)
	
	head = new_soup.new_tag('head')
	html.append(head)
	
	title = new_soup.new_tag('title')
	title.string = soup.title.string if soup.title else "Reddit"
	head.append(title)
	
	body = new_soup.new_tag('body')
	html.append(body)
	
	table = new_soup.new_tag('table', width="100%")
	body.append(table)
	tr = new_soup.new_tag('tr')
	table.append(tr)
	
	left_cell = new_soup.new_tag('td', align="left")
	right_cell = new_soup.new_tag('td', align="right")
	tr.append(left_cell)
	tr.append(right_cell)
	
	left_font = new_soup.new_tag('font', size="4")
	left_cell.append(left_font)
	
	b1 = new_soup.new_tag('b')
	b1.string = "reddit"
	left_font.append(b1)
	
	parts = url.split('reddit.com', 1)[1].split('/')
	if len(parts) > 2 and parts[1] == 'r':
		subreddit = parts[2]
		left_font.append(" | ")
		s = new_soup.new_tag('span')
		s.string = f"r/{subreddit}".lower()
		left_font.append(s)
	
	# Add tabmenu items for non-comment pages
	if "/comments/" not in url:
		tabmenu = soup.find('ul', class_='tabmenu')
		if tabmenu:
			right_font = new_soup.new_tag('font', size="4")
			right_cell.append(right_font)
			menu_items = tabmenu.find_all('li')
			for li in menu_items:
				a = li.find('a')
				if a and a.string in ['hot', 'new', 'top']:
					if 'selected' in li.get('class', []):
						right_font.append(a.string)
					else:
						href = a['href']
						if href.startswith(('http://old.reddit.com', 'https://old.reddit.com')):
							href = href.replace('//old.reddit.com', '//reddit.com', 1)
						new_a = new_soup.new_tag('a', href=href)
						new_a.string = a.string
						right_font.append(new_a)
					right_font.append(" ")
	
	hr = new_soup.new_tag('hr')
	body.append(hr)
	
	if "/comments/" in url:
		body.append(new_soup.new_tag('br'))
		
		thing = soup.find('div', id=lambda x: x and x.startswith('thing_'))
		if thing:
			top_matter = thing.find('div', class_='top-matter')
			if top_matter:
				title_a = top_matter.find('a')
				tagline = top_matter.find('p', class_='tagline', recursive=False)
				
				if title_a:
					d = new_soup.new_tag('div')
					dl = new_soup.new_tag('dl')
					dt = new_soup.new_tag('dt')
					original_href = title_a.get('href', '')
					# If link is external (not a reddit self post), make it clickable via outbound proxy
					title_font = new_soup.new_tag('font', size="4")
					if original_href and 'reddit.com' not in original_href:
						import urllib.parse
						outbound_url = 'http://reddit.com/outbound?url=' + urllib.parse.quote(original_href, safe='')
						a_tag = new_soup.new_tag('a', href=outbound_url)
						b = new_soup.new_tag('b')
						b.string = title_a.string
						a_tag.append(b)
						title_font.append(a_tag)
					else:
						b = new_soup.new_tag('b')
						b.string = title_a.string
						title_font.append(b)
					dt.append(title_font)
					dl.append(dt)

					dd = new_soup.new_tag('dd')
					font = new_soup.new_tag('font', size="2")
					if tagline:
						time_element = tagline.find('time', class_='live-timestamp')
						author_element = tagline.find('a', class_='author')
						
						font.append("submitted ")
						if time_element:
							font.append(time_element.string)
						font.append(" by ")
						if author_element:
							b_author = new_soup.new_tag('b')
							b_author.string = author_element.string
							font.append(b_author)
					dl.append(dd)
					dd.append(font)
					d.append(dl)
					
					# Add preview images if they exist and are not in gallery-tile-content
					preview_imgs = soup.find_all('img', class_='preview')
					valid_imgs = [img for img in preview_imgs if img.find_parent('div', class_='gallery-tile-content') is None]
					if valid_imgs:
						d.append(new_soup.new_tag('br'))
						d.append(new_soup.new_tag('br'))
						for img in valid_imgs:
							enclosing_a = img.find_parent('a')
							if enclosing_a and enclosing_a.has_attr('href'):
								img_src = enclosing_a['href']
								new_img = new_soup.new_tag('img', src=img_src, width="50", height="40")
								d.append(new_img)
								d.append(" ")  # Add space between images
				
					# Add post content if it exists
					usertext_body = thing.find('div', class_='usertext-body')
					if usertext_body:
						md_content = usertext_body.find('div', class_='md')
						if md_content:
							d.append(new_soup.new_tag('br'))
							d.append(md_content)
					
					body.append(d)

		# Add a <br> before the <hr> that divides comments and the original post
		body.append(new_soup.new_tag('br'))
		body.append(new_soup.new_tag('br'))
		body.append(new_soup.new_tag('hr'))

		# Add comments (limited to keep load times sane)
		MAX_TOP_COMMENTS = 10
		MAX_REPLY_DEPTH = 3
		comments_area = soup.find('div', class_='sitetable nestedlisting')
		if comments_area:
			comments_div = new_soup.new_tag('div')
			body.append(comments_div)
			process_comments(comments_area, comments_div, new_soup, depth=0, max_top=MAX_TOP_COMMENTS, max_depth=MAX_REPLY_DEPTH)
	else:
		site_table = soup.find('div', id='siteTable')
		if site_table:
			for thing in site_table.find_all('div', id=lambda x: x and x.startswith('thing_'), recursive=False):
				title_a = thing.find('a', class_='title')
				permalink = thing.get('data-permalink', '')
				
				if (title_a and 
					'alb.reddit.com' not in title_a.get('href', '') and 
					not permalink.startswith('/user/')):
					
					if permalink:
						title_a['href'] = f"http://reddit.com{permalink}"
					
					dl = new_soup.new_tag('dl')
					
					dt = new_soup.new_tag('dt')
					dt.append(title_a)
					dl.append(dt)
					
					dd = new_soup.new_tag('dd')
					font = new_soup.new_tag('font', size="2")
					author = thing.get('data-author', 'Unknown')
					font.append(f"{author} | ")
					
					time_element = thing.find('time', class_='live-timestamp')
					if time_element:
						font.append(time_element.string)
					else:
						font.append("Unknown time")
					
					buttons = thing.find('ul', class_='buttons')
					if buttons:
						comments_li = buttons.find('li', class_='first')
						if comments_li:
							comments_a = comments_li.find('a', class_='comments')
							if comments_a:
								font.append(f" | {comments_a.string}")
					
					# Add points
					points = thing.get('data-score', 'Unknown')
					font.append(f" | {points} points")
					
					dd.append(font)
					dl.append(dd)
					
					body.append(dl)

		# Add navigation buttons
		nav_buttons = soup.find('div', class_='nav-buttons')
		if nav_buttons:
			center_tag = new_soup.new_tag('center')
			body.append(center_tag)

			nav_table = new_soup.new_tag('table', width="100%")
			nav_tr = new_soup.new_tag('tr')
			nav_left = new_soup.new_tag('td', align="center")
			nav_right = new_soup.new_tag('td', align="center")
			nav_tr.append(nav_left)
			nav_tr.append(nav_right)
			nav_table.append(nav_tr)
			center_tag.append(nav_table)

			prev_button = nav_buttons.find('span', class_='prev-button')
			if prev_button and prev_button.find('a'):
				prev_link = prev_button.find('a')
				new_prev = new_soup.new_tag('a', href=prev_link['href'].replace('old.reddit.com', 'reddit.com'))
				new_prev.string = '&lt; prev'
				nav_left.append(new_prev)

			next_button = nav_buttons.find('span', class_='next-button')
			if next_button and next_button.find('a'):
				next_link = next_button.find('a')
				new_next = new_soup.new_tag('a', href=next_link['href'].replace('old.reddit.com', 'reddit.com'))
				new_next.string = 'next &gt;'
				nav_right.append(new_next)

	updated_html = str(new_soup)

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
	return ''.join(cleaned), 200