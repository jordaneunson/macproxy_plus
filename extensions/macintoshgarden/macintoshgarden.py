import requests
from bs4 import BeautifulSoup
from flask import Response
import urllib.parse
import re
import time

DOMAIN = "macintoshgarden.org"

# Download URL registry — maps short IDs to real download URLs
# Keyed by index (int), value is (timestamp, url, detail_path, fname, cookies_dict)
_download_registry = {}
_download_counter = 0
_DOWNLOAD_TTL = 3600  # 1 hour

# Persistent session for all macintoshgarden.org requests — maintains cookies
_http_session = requests.Session()
_http_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
})

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
}

BASE_URL = "https://www.macintoshgarden.org"

CHAR_MAP = {
    '\u2018': "'", '\u2019': "'", '\u201C': '"', '\u201D': '"',
    '\u2013': '-', '\u2014': '--', '\u2026': '...', '\u00A0': ' ',
    '\u2032': "'", '\u2033': '"', '\u00AB': '<<', '\u00BB': '>>',
    '\u2022': '*', '\u00B7': '*', '\u2010': '-', '\u2011': '-',
    '\u2012': '-', '\u2015': '--', '\u2212': '-', '\u00D7': 'x',
    '\u00F7': '/', '\u2190': '<-', '\u2192': '->', '\u2264': '<=',
    '\u2265': '>=', '\u00A9': '(c)', '\u00AE': '(R)', '\u2122': '(TM)',
    '\u00BC': '1/4', '\u00BD': '1/2', '\u00BE': '3/4', '\u00B0': ' deg',
}


def clean_text(text):
    for char, replacement in CHAR_MAP.items():
        text = text.replace(char, replacement)
    cleaned = []
    for ch in text:
        if ord(ch) < 128:
            cleaned.append(ch)
        else:
            cleaned.append('?')
    return ''.join(cleaned)


def make_page(title, body_html):
    html = '<html>\n<head><title>' + clean_text(title) + '</title></head>\n<body>\n' + search_bar() + '\n<hr>\n' + body_html + '\n<hr>\n' + footer() + '\n</body>\n</html>'
    return clean_text(html), 200


def search_bar():
    return '''<center>
<a href="http://macintoshgarden.org/apps">Apps</a>
&nbsp;|&nbsp;<a href="http://macintoshgarden.org/games">Games</a>
&nbsp;|&nbsp;<a href="http://macintoshgarden.org/guides">Guides</a>
&nbsp;|&nbsp;<a href="http://macintoshgarden.org/forum">Forum</a>
&nbsp;|&nbsp;<a href="http://macintoshgarden.org/ftp">FTP</a>
&nbsp;|&nbsp;<a href="http://macintoshgarden.org/about">About</a>
<br>
<form action="http://macintoshgarden.org/search" method="get">
<input type="text" name="q" size="30">
<input type="submit" value="Search">
</form>
</center>'''


def footer():
    return '<center><font size="2">Macintosh Garden - Classic Mac Software Archive</font></center>'


def error_page(message, status=500):
    body = '<p><b>Error:</b> ' + message + '</p><p><a href="http://macintoshgarden.org/">Return to homepage</a></p>'
    html = '<html>\n<head><title>Error - Macintosh Garden</title></head>\n<body>\n' + search_bar() + '\n<hr>\n' + body + '\n</body>\n</html>'
    return clean_text(html), status


def fetch(url, ttl=None):
    resp = _http_session.get(url, timeout=15, allow_redirects=True)
    resp.raise_for_status()
    return resp





def handle_request(request):
    path = request.path
    query_string = request.query_string.decode('utf-8', errors='replace')

    # Route: search
    if path == '/search' or path.startswith('/search/node'):
        q = request.args.get('q', '')
        if not q:
            m = re.match(r'^/search/node/(.+)$', path)
            if m:
                q = urllib.parse.unquote_plus(m.group(1))
        if not q:
            return handle_homepage()
        return handle_search(q)

    # Route: homepage
    if path == '/' or path == '':
        return handle_homepage()

    # Route: apps or games listing (bare, /all, single letter like /a, /b, or with ?page=)
    if re.match(r'^/(apps|games)(/all|/[a-z0-9])?(\?.*)?$', path):
        return handle_listing(path)

    # Route: download proxy
    if path.startswith('/download/'):
        return handle_download(request)

    # Fallback: try to proxy the page as a detail page
    return handle_detail(path)


# ---------------------------------------------------------------------------
# Homepage
# ---------------------------------------------------------------------------

def handle_homepage():
    try:
        content = fetch(BASE_URL + "/").content
        soup = BeautifulSoup(content, 'html.parser')
    except Exception as e:
        return error_page(str(e))

    body = []
    body.append('<center><h2>Macintosh Garden</h2>')
    body.append('<p>Classic Macintosh Software Archive</p>')
    body.append('<table width="80%" border="1" cellpadding="4">')
    body.append('<tr>')
    body.append('<td align="center"><b><a href="http://macintoshgarden.org/apps">Applications</a></b><br>Productivity, utilities, and more</td>')
    body.append('<td align="center"><b><a href="http://macintoshgarden.org/games">Games</a></b><br>Classic Mac games</td>')
    body.append('</tr>')
    body.append('</table></center>')
    body.append('<br>')

    items = []
    for node in soup.select('div.views-row, div.node-teaser, article'):
        title_tag = node.find(['h2', 'h3', 'h4'])
        if not title_tag:
            continue
        a_tag = title_tag.find('a')
        if not a_tag:
            continue
        title = a_tag.get_text(strip=True)
        href = a_tag.get('href', '')
        if not href or href == '#':
            continue
        if not href.startswith('http'):
            href = 'http://macintoshgarden.org' + href
        else:
            href = href.replace('https://', 'http://')

        snippet = ''
        body_div = node.find('div', class_=re.compile(r'field-body|body|teaser|summary'))
        if body_div:
            snippet = body_div.get_text(strip=True)[:120]
            if len(snippet) == 120:
                snippet += '...'

        items.append((title, href, snippet))

    if items:
        body.append('<b>Recent Additions</b>')
        body.append('<hr>')
        body.append('<dl>')
        for title, href, snippet in items[:20]:
            body.append('<dt><a href="' + href + '">' + title + '</a></dt>')
            if snippet:
                body.append('<dd><font size="2">' + snippet + '</font></dd>')
        body.append('</dl>')
    else:
        body.append('<p>Browse the archive using the links above.</p>')

    return make_page("Macintosh Garden", '\n'.join(body))


# ---------------------------------------------------------------------------
# Listing (Apps / Games)
# ---------------------------------------------------------------------------

def handle_listing(path):
    category = 'apps' if path.startswith('/apps') else 'games'
    category_label = 'Applications' if category == 'apps' else 'Games'
    target = BASE_URL + path

    try:
        content = fetch(target).content
        soup = BeautifulSoup(content, 'html.parser')
    except Exception as e:
        return error_page(str(e))

    body = []
    body.append('<h2>' + category_label + '</h2>')

    # --- Alphabet navigation ---
    alpha_links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)
        if re.match(r'^[0-9A-Za-z]$', text) and '/' + category in href:
            alpha_links.append((text.upper(), href))

    seen = set()
    unique_alpha = []
    for label, href in alpha_links:
        if label not in seen:
            seen.add(label)
            unique_alpha.append((label, href))

    if unique_alpha:
        body.append('<p>')
        for label, href in unique_alpha:
            h = href if href.startswith('http') else 'http://macintoshgarden.org' + href
            h = h.replace('https://', 'http://')
            body.append('<a href="' + h + '">[' + label + ']</a> ')
        body.append('</p>')
        body.append('<hr>')

    # --- Item listing ---
    items = []
    for node in soup.select('div.views-row, li.views-row, div.node-teaser'):
        a_tag = node.find('a', href=True)
        if not a_tag:
            continue
        title = a_tag.get_text(strip=True)
        href = a_tag['href']
        if not href or href == '#':
            continue
        if not href.startswith('http'):
            href = 'http://macintoshgarden.org' + href
        else:
            href = href.replace('https://', 'http://')

        if href.rstrip('/') in ('http://macintoshgarden.org/apps', 'http://macintoshgarden.org/games'):
            continue

        meta = ''
        meta_div = node.find('div', class_=re.compile(r'field-created|field-author|date|submitted'))
        if meta_div:
            meta = meta_div.get_text(strip=True)[:60]

        items.append((title, href, meta))

    if items:
        body.append('<dl>')
        for title, href, meta in items:
            body.append('<dt><a href="' + href + '">' + title + '</a></dt>')
            if meta:
                body.append('<dd><font size="2">' + meta + '</font></dd>')
        body.append('</dl>')
    else:
        body.append('<p>No items found. Try browsing by letter above.</p>')

    # --- Pagination ---
    pager = soup.find('ul', class_=re.compile(r'pager'))
    if pager:
        body.append('<p align="center">')
        for li in pager.find_all('li'):
            a = li.find('a')
            if a:
                href = a['href']
                if not href.startswith('http'):
                    href = 'http://macintoshgarden.org' + href
                else:
                    href = href.replace('https://', 'http://')
                label = a.get_text(strip=True) or li.get_text(strip=True)
                body.append('<a href="' + href + '">[' + label + ']</a> ')
            else:
                label = li.get_text(strip=True)
                if label:
                    body.append('<b>[' + label + ']</b> ')
        body.append('</p>')

    return make_page(category_label + ' - Macintosh Garden', '\n'.join(body))


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def handle_search(query):
    encoded = urllib.parse.quote(query)
    target = BASE_URL + "/search/node/" + encoded

    try:
        content = fetch(target).content
        soup = BeautifulSoup(content, 'html.parser')
    except Exception as e:
        return error_page(str(e))

    body = []
    body.append('<h2>Search: ' + query + '</h2>')
    body.append('<hr>')

    results = []

    # Site uses <dl class="search-results"> with <dt>/<dd> pairs
    for dt in soup.select('dl.search-results dt.title'):
        a_tag = dt.find('a', href=True)
        if not a_tag:
            continue
        title = a_tag.get_text(strip=True)
        href = a_tag['href']
        if not href.startswith('http'):
            href = 'http://macintoshgarden.org' + href
        else:
            href = href.replace('https://', 'http://')

        snippet = ''
        category = ''
        dd = dt.find_next_sibling('dd')
        if dd:
            snippet_p = dd.find('p', class_='search-snippet')
            if snippet_p:
                snippet = snippet_p.get_text(strip=True)[:150]
                if len(snippet) == 150:
                    snippet += '...'
            info_p = dd.find('p', class_='search-info')
            if info_p:
                info_text = info_p.get_text(strip=True)
                # First word is usually the type (Game, App, etc.)
                parts = info_text.split(' - ', 1)
                if parts:
                    category = parts[0].strip()

        results.append((title, href, snippet, category))

    if results:
        body.append('<p><font size="2">' + str(len(results)) + ' result(s) found</font></p>')
        body.append('<dl>')
        for title, href, snippet, category in results:
            cat_str = ' <font size="2">[' + category + ']</font>' if category else ''
            body.append('<dt><a href="' + href + '">' + title + '</a>' + cat_str + '</dt>')
            if snippet:
                body.append('<dd><font size="2">' + snippet + '</font></dd>')
        body.append('</dl>')
    else:
        body.append('<p>No results found for "' + query + '".</p>')
        body.append('<p>Try browsing: <a href="http://macintoshgarden.org/apps">Apps</a> | <a href="http://macintoshgarden.org/games">Games</a></p>')

    # Pagination
    pager = soup.find('ul', class_=re.compile(r'pager'))
    if pager:
        body.append('<p align="center">')
        for li in pager.find_all('li'):
            a = li.find('a')
            if a:
                href = a['href']
                if not href.startswith('http'):
                    href = 'http://macintoshgarden.org' + href
                else:
                    href = href.replace('https://', 'http://')
                label = a.get_text(strip=True) or li.get_text(strip=True)
                body.append('<a href="' + href + '">[' + label + ']</a> ')
            else:
                label = li.get_text(strip=True)
                if label:
                    body.append('<b>[' + label + ']</b> ')
        body.append('</p>')

    return make_page('Search: ' + query + ' - Macintosh Garden', '\n'.join(body))


# ---------------------------------------------------------------------------
# Detail page
# ---------------------------------------------------------------------------

def handle_detail(path):
    target = BASE_URL + path
    try:
        # Always fetch fresh — download tokens expire in ~5 minutes,
        # so cached pages would have dead tokens
        resp = fetch(target)
        content = resp.content
        soup = BeautifulSoup(content, 'html.parser')
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return error_page('Page not found.', 404)
        return error_page(str(e))
    except Exception as e:
        return error_page(str(e))

    body = []

    # --- Title ---
    page_title = ''
    title_tag = soup.find('h1', class_=re.compile(r'title|page-title')) or soup.find('h1')
    if title_tag:
        page_title = title_tag.get_text(strip=True)

    if not page_title:
        title_el = soup.find('title')
        page_title = title_el.get_text(strip=True) if title_el else 'Macintosh Garden'

    body.append('<h2>' + page_title + '</h2>')
    body.append('<hr>')

    # --- Metadata table ---
    meta_rows = []
    for field in soup.select('div.field'):
        label_el = field.find(class_=re.compile(r'field-label'))
        value_el = field.find(class_=re.compile(r'field-item|field-items'))
        if label_el and value_el:
            label = label_el.get_text(strip=True).rstrip(':')
            value = value_el.get_text(strip=True)
            if label and value:
                meta_rows.append((label, value))

    compat_text = ''
    for tag in soup.find_all(string=re.compile(r'68k|PPC|PowerPC', re.I)):
        parent = tag.parent
        if parent:
            compat_text = parent.get_text(strip=True)[:100]
            break

    if meta_rows:
        body.append('<table border="0" cellpadding="3">')
        for label, value in meta_rows[:12]:
            body.append('<tr><td><b>' + label + ':</b></td><td>' + value + '</td></tr>')
        body.append('</table>')
        body.append('<br>')

    # --- Description ---
    desc_div = (
        soup.find('div', class_=re.compile(r'field-name-body|body|description'))
        or soup.find('div', class_='content')
    )
    if desc_div:
        for tag in desc_div.find_all(['script', 'style', 'img']):
            tag.decompose()
        desc_text = desc_div.get_text(separator=' ', strip=True)[:800]
        if len(desc_text) == 800:
            desc_text += '...'
        body.append('<b>Description:</b>')
        body.append('<blockquote>' + desc_text + '</blockquote>')

    if compat_text:
        body.append('<p><b>Compatibility:</b> ' + compat_text + '</p>')

    body.append('<hr>')

    # --- Download links ---
    body.append('<b>Downloads:</b>')
    body.append('<br>')

    download_links = _extract_downloads(soup, path)

    if download_links:
        body.append('<table border="1" cellpadding="4" width="100%">')
        body.append('<tr><th>File</th><th>Size</th><th>Mirrors</th></tr>')
        for dl in download_links:
            fname = dl['filename']
            size = dl['size'] or ''
            mirror_html = dl['mirror_html']
            proxy_href = dl['proxy_url']
            body.append('<tr>')
            body.append('<td><a href="' + proxy_href + '"><b>' + fname + '</b></a></td>')
            body.append('<td>' + size + '</td>')
            body.append('<td>' + mirror_html + '</td>')
            body.append('</tr>')
        body.append('</table>')
        body.append('<br>')
        body.append('<font size="2">Click a filename to download via MacProxy.</font>')
    else:
        body.append('<p>No download links found on this page.</p>')

    return make_page(page_title + ' - Macintosh Garden', '\n'.join(body))


def _extract_downloads(soup, path):
    """Extract download links, grouping all mirrors per file."""
    seen_hrefs = set()

    MIRROR_PATTERNS = [
        r'download\.macintoshgarden\.org',
        r'macintoshgarden\.org\.se',
        r'macintoshgarden\.r-fx\.ca',
        r'files\.macintoshgarden\.org',
        r'macintoshgarden\.org\.de',
        r'ftp\.macintoshgarden',
        r'old\.mac\.gdn',
        r'www\.macintoshgarden\.org/files',
        r'macintoshgarden\.org/files',
    ]
    mirror_re = re.compile('|'.join(MIRROR_PATTERNS), re.I)
    file_ext_re = re.compile(r'\.(sit|hqx|bin|zip|img|dsk|sea|cpt|tar|gz|dmg|toast|iso|7z|pdf)(\?.*)?$', re.I)

    # Collect all download links grouped by filename
    # file_groups[fname_key] = { 'filename': ..., 'size': ..., 'mirrors': [ {label, url, proxy_url}, ... ] }
    file_groups = {}
    file_order = []  # preserve order

    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)

        is_mirror = bool(mirror_re.search(href))
        is_file = bool(file_ext_re.search(href))

        if not (is_mirror or is_file):
            continue

        # Skip screenshots, images, and md5 check links
        if re.search(r'\.(png|jpg|jpeg|gif|webp)(\?.*)?$', href, re.I):
            continue
        if 'arch_md5.php' in href:
            continue
        if '/screenshots/' in href:
            continue

        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)

        # Normalize the URL
        real_url = href
        if real_url.startswith('//'):
            real_url = 'https:' + real_url
        elif not real_url.startswith('http'):
            real_url = 'https://' + real_url.lstrip('/')
        if real_url.startswith('http://'):
            real_url = real_url.replace('http://', 'https://', 1)

        # Determine mirror label
        mirror_label = 'WWW'
        if 'download.macintoshgarden.org' in href:
            mirror_label = 'Main'
        elif '.se' in href:
            mirror_label = '.SE'
        elif '.de' in href:
            mirror_label = '.DE'
        elif 'r-fx.ca' in href:
            mirror_label = 'CA'
        elif 'files.macintoshgarden.org' in href:
            mirror_label = 'Files'
        elif 'ftp.macintoshgarden' in href:
            mirror_label = 'FTP'
        elif 'old.mac.gdn' in href:
            mirror_label = 'Old'

        fname = href.split('/')[-1].split('?')[0] or text or 'download'
        fname_key = fname.lower()

        # Try to get file size from adjacent table cell
        size = ''
        td = a.find_parent('td')
        if td:
            next_td = td.find_next_sibling('td')
            if next_td:
                candidate = next_td.get_text(strip=True)
                if re.match(r'^\d+', candidate):
                    size = candidate

        # Register download for this mirror
        proxy_url = _register_download(real_url, path)

        if fname_key not in file_groups:
            file_groups[fname_key] = {
                'filename': fname,
                'size': size,
                'mirrors': [],
            }
            file_order.append(fname_key)
        elif size and not file_groups[fname_key]['size']:
            file_groups[fname_key]['size'] = size

        file_groups[fname_key]['mirrors'].append({
            'label': mirror_label,
            'proxy_url': proxy_url,
        })

    # Build flat download list with mirror links
    downloads = []
    for fname_key in file_order:
        group = file_groups[fname_key]
        # First mirror is the primary download link
        primary_url = group['mirrors'][0]['proxy_url']
        # Build mirror column with all links
        mirror_links = []
        for m in group['mirrors']:
            mirror_links.append('<a href="' + m['proxy_url'] + '">' + m['label'] + '</a>')
        mirror_html = ' | '.join(mirror_links)

        downloads.append({
            'filename': group['filename'],
            'size': group['size'],
            'mirror_html': mirror_html,
            'proxy_url': primary_url,
        })

    return downloads


# ---------------------------------------------------------------------------
# Download proxy
# ---------------------------------------------------------------------------

def _register_download(url, detail_path):
    """Store the full tokenized download URL and session cookies."""
    global _download_counter
    # Evict expired entries
    now = time.time()
    expired = [k for k, v in _download_registry.items() if now - v[0] > _DOWNLOAD_TTL]
    for k in expired:
        del _download_registry[k]

    _download_counter += 1
    fname = url.split('/')[-1].split('?')[0] or 'download.bin'
    # Snapshot current session cookies so the download can reuse them
    cookies = dict(_http_session.cookies)
    _download_registry[_download_counter] = (now, url, detail_path, fname, cookies)
    print("[macintoshgarden] Registered download #%d: %s (from %s) cookies=%s" % (_download_counter, fname, detail_path, list(cookies.keys())))
    return 'http://macintoshgarden.org/download/' + str(_download_counter) + '/' + fname


def handle_download(request):
    """Proxy the actual file download so a vintage Mac can grab it."""
    path = request.path  # /download/<id>/<filename>
    parts = path[len('/download/'):].split('/', 1)
    dl_id_str = parts[0]

    if not dl_id_str:
        return error_page('No download URL specified.', 400)

    try:
        dl_id = int(dl_id_str)
    except ValueError:
        return error_page('Invalid download link.', 400)

    now_ts = time.time()
    print("[macintoshgarden] Download request for ID %d, registry has %s, now=%s" % (dl_id, list(_download_registry.keys()), now_ts))
    entry = _download_registry.get(dl_id)
    if entry:
        print("[macintoshgarden] Entry timestamp=%s, age=%.1fs, TTL=%ds" % (entry[0], now_ts - entry[0], _DOWNLOAD_TTL))
    if not entry:
        return error_page('Download link expired or not found. Go back and try again.', 404)

    timestamp, file_url, detail_path, target_fname, cookies = entry
    age = time.time() - timestamp
    if age > _DOWNLOAD_TTL:
        del _download_registry[dl_id]
        return error_page('Download link expired. Go back and try again.', 410)

    # Use the stored token URL directly — page is fetched fresh (no cache)
    # so tokens should be live when the user clicks
    referer_url = BASE_URL + detail_path
    _http_session.cookies.update(cookies)

    print("[macintoshgarden] Downloading %s with Referer: %s cookies=%s" % (file_url[:120], referer_url, list(cookies.keys())))

    try:
        # Download entire file — no chunked encoding.
        # MacWeb 2.0 (HTTP/1.0) can't handle chunked transfer.
        dl_resp = _http_session.get(
            file_url,
            headers={'Referer': referer_url},
            timeout=120,
            allow_redirects=True
        )

        # Log full request/response details for debugging
        print("[macintoshgarden] === REQUEST DETAILS ===")
        print("[macintoshgarden] URL: %s" % file_url)
        print("[macintoshgarden] Request headers: %s" % dict(dl_resp.request.headers))
        print("[macintoshgarden] === RESPONSE DETAILS ===")
        print("[macintoshgarden] Status: %d" % dl_resp.status_code)
        print("[macintoshgarden] Response headers: %s" % dict(dl_resp.headers))
        if dl_resp.status_code >= 400:
            print("[macintoshgarden] Response body: %s" % dl_resp.text[:500])
        dl_resp.raise_for_status()

        data = dl_resp.content
        content_type = dl_resp.headers.get('Content-Type', 'application/octet-stream')

        fname = target_fname or 'download.bin'
        response_headers = {
            'Content-Type': content_type,
            'Content-Length': str(len(data)),
            'Content-Disposition': 'attachment; filename="' + fname + '"',
        }

        print("[macintoshgarden] Download OK: %s (%d bytes)" % (fname, len(data)))
        return Response(
            data,
            status=200,
            headers=response_headers
        )

    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else 500
        print("[macintoshgarden] Download FAILED: HTTP %d for %s" % (code, file_url[:100]))
        return error_page('Download failed (HTTP %d). The token may have expired — go back to the detail page and try again.' % code, code)
    except Exception as e:
        print("[macintoshgarden] Download ERROR: %s" % str(e))
        return error_page('Download error: ' + str(e))
