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
import time
import urllib.parse

DOMAIN = "reddit.com"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"

# --- Caches ---
# Page cache: URL -> (timestamp, response_content_bytes)
_page_cache = {}
_PAGE_CACHE_TTL = 180  # 3 minutes
_MAX_PAGE_CACHE = 50

# Image cache: image_url -> (timestamp, dithered_img_tag_html)
_image_cache = {}
_IMAGE_CACHE_TTL = 900  # 15 minutes
_MAX_IMAGE_CACHE = 200


def _cache_get(cache, key, ttl):
	"""Get from cache if not expired."""
	if key in cache:
		ts, val = cache[key]
		if time.time() - ts < ttl:
			return val
		del cache[key]
	return None


def _cache_put(cache, key, val, ttl, max_entries):
	"""Put into cache, evicting expired/oldest if full."""
	now = time.time()
	if len(cache) >= max_entries:
		expired = [k for k, (t, _) in cache.items() if now - t > ttl]
		for k in expired:
			del cache[k]
		if len(cache) >= max_entries:
			oldest = sorted(cache, key=lambda k: cache[k][0])
			for k in oldest[:len(oldest) // 2]:
				del cache[k]
	cache[key] = (now, val)


def _fetch_reddit(url):
	"""Fetch a Reddit page with caching."""
	# Strip cpage param for cache key since it's our own pagination
	cache_key = url.split('?')[0] if '?cpage=' in url else url
	cached = _cache_get(_page_cache, cache_key, _PAGE_CACHE_TTL)
	if cached is not None:
		return cached
	headers = {'User-Agent': USER_AGENT}
	resp = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
	resp.raise_for_status()
	_cache_put(_page_cache, cache_key, resp.content, _PAGE_CACHE_TTL, _MAX_PAGE_CACHE)
	return resp.content


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
		content = _fetch_reddit(url)
		return process_content(content, url, request)
	except requests.RequestException as e:
		return Response(f"An error occurred: {str(e)}", status=500)


def handle_outbound(target_url):
	"""Fetch an external page linked from Reddit, strip images and heavy content."""
	try:
		headers = {'User-Agent': USER_AGENT}
		resp = requests.get(target_url, headers=headers, allow_redirects=True, timeout=15)
		resp.raise_for_status()
	except requests.RequestException as e:
		return f"<html><head><title>Error</title></head><body><p><b>Could not load article:</b> {str(e)}</p><p><a href=\"http://reddit.com/\">Back to Reddit</a></p></body></html>", 500

	soup = BeautifulSoup(resp.content, 'html.parser')

	page_title = soup.title.string.strip() if soup.title and soup.title.string else target_url

	for tag in soup.find_all(['img', 'script', 'style', 'iframe', 'video', 'audio',
							  'svg', 'canvas', 'noscript', 'picture', 'source', 'figure']):
		tag.decompose()

	for tag in soup.find_all(True):
		if tag.has_attr('style'):
			del tag['style']
		if tag.has_attr('class'):
			del tag['class']

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
		body_tag = soup.find('body')
		body_text = body_tag.get_text(separator='\n', strip=True) if body_tag else ''

	lines = [line.strip() for line in body_text.split('\n')]
	lines = [line for line in lines if line]
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

	return html, 200


def process_comments(comments, parent_element, new_soup, depth=0, max_depth=None):
	"""Process a list of comment elements directly (no re-parsing)."""
	for comment in comments:
		if max_depth is not None and depth >= max_depth:
			return

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

		comment_div.append(new_soup.new_tag('br'))

		# Process child comments
		child_area = comment.find('div', class_='child')
		if child_area:
			child_comments = child_area.find('div', class_='sitetable listing')
			if child_comments:
				child_list = [c for c in child_comments.find_all('div', class_='thing', recursive=False) if 'comment' in c.get('class', [])]
				process_comments(child_list, comment_div, new_soup, depth + 1, max_depth=max_depth)


def process_content(content, url, request=None):
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
					title_font = new_soup.new_tag('font', size="4")
					if original_href and 'reddit.com' not in original_href:
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
								d.append(" ")
				
					# Add post content if it exists
					usertext_body = thing.find('div', class_='usertext-body')
					if usertext_body:
						md_content = usertext_body.find('div', class_='md')
						if md_content:
							# Rewrite external links to go through outbound proxy
							for a in md_content.find_all('a', href=True):
								href = a['href']
								if href and 'reddit.com' not in href and href.startswith(('http://', 'https://')):
									a['href'] = 'http://reddit.com/outbound?url=' + urllib.parse.quote(href, safe='')
							d.append(new_soup.new_tag('br'))
							d.append(md_content)
					
					body.append(d)

		body.append(new_soup.new_tag('br'))
		body.append(new_soup.new_tag('br'))
		body.append(new_soup.new_tag('hr'))

		# Add comments (paginated to keep load times sane)
		COMMENTS_PER_PAGE = 3
		MAX_REPLY_DEPTH = 3
		comments_area = soup.find('div', class_='sitetable nestedlisting')
		if comments_area:
			# Get all top-level comments directly from the already-parsed tree
			all_top_comments = [c for c in comments_area.find_all('div', class_='thing', recursive=False) if 'comment' in c.get('class', [])]
			total_comments = len(all_top_comments)

			# Determine current page
			cpage = int(request.args.get('cpage', '1')) if request else 1
			if cpage < 1:
				cpage = 1
			start = (cpage - 1) * COMMENTS_PER_PAGE
			end = start + COMMENTS_PER_PAGE
			total_pages = (total_comments + COMMENTS_PER_PAGE - 1) // COMMENTS_PER_PAGE

			if total_comments > COMMENTS_PER_PAGE:
				page_info = new_soup.new_tag('p')
				page_info_font = new_soup.new_tag('font', size="2")
				page_info_font.string = f"Comments {start + 1}-{min(end, total_comments)} of {total_comments} (page {cpage}/{total_pages})"
				page_info.append(page_info_font)
				body.append(page_info)

			comments_div = new_soup.new_tag('div')
			body.append(comments_div)

			# Slice directly from the parsed tree — no re-serialization or re-parsing
			page_comments = all_top_comments[start:end]
			process_comments(page_comments, comments_div, new_soup, depth=0, max_depth=MAX_REPLY_DEPTH)

			# Pagination links
			if total_pages > 1:
				base_path = url.replace('old.reddit.com', 'reddit.com')
				if '?' in base_path:
					base_path = base_path.split('?')[0]

				nav_p = new_soup.new_tag('p', align="center")
				body.append(nav_p)

				if cpage > 1:
					prev_a = new_soup.new_tag('a', href=f"{base_path}?cpage={cpage - 1}")
					prev_a.string = "< prev"
					nav_p.append(prev_a)
					nav_p.append(" ")

				for p in range(1, total_pages + 1):
					if p == cpage:
						b_tag = new_soup.new_tag('b')
						b_tag.string = f"[{p}]"
						nav_p.append(b_tag)
					else:
						page_a = new_soup.new_tag('a', href=f"{base_path}?cpage={p}")
						page_a.string = f"[{p}]"
						nav_p.append(page_a)
					nav_p.append(" ")

				if cpage < total_pages:
					next_a = new_soup.new_tag('a', href=f"{base_path}?cpage={cpage + 1}")
					next_a.string = "next >"
					nav_p.append(next_a)
	else:
		site_table = soup.find('div', id='siteTable')
		if site_table:
			for thing in site_table.find_all('div', id=lambda x: x and x.startswith('thing_'), recursive=False):
				title_a = thing.find('a', class_='title')
				permalink = thing.get('data-permalink', '')
				
				if (title_a and 
					'alb.reddit.com' not in title_a.get('href', '') and 
					not permalink.startswith('/user/')):
					
					# Build a clean <a> tag — strip all the data-* and tracking attributes
					clean_href = f"http://reddit.com{permalink}" if permalink else title_a.get('href', '')
					clean_a = new_soup.new_tag('a', href=clean_href)
					clean_a.string = title_a.string or title_a.get_text(strip=True)
					
					dl = new_soup.new_tag('dl')
					
					dt = new_soup.new_tag('dt')
					dt.append(clean_a)
					dl.append(dt)
					
					dd = new_soup.new_tag('dd')
					font = new_soup.new_tag('font', size="2")
					author = thing.get('data-author', 'Unknown')
					subreddit = thing.get('data-subreddit', '')
					if subreddit:
						font.append(f"r/{subreddit} | ")
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
	return updated_html, 200
