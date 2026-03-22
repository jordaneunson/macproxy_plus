from flask import request
import requests
import json
import re
import random

DOMAIN = "jordaneunson.com"

BASE_URL = "https://jordaneunson.com"
MANIFEST_URL = f"{BASE_URL}/gastro.recipes/manifest.json"
RECIPE_BASE = f"{BASE_URL}/gastro.recipes/"

HEADERS = {"User-Agent": "macproxybot/1.0"}


def fetch_manifest():
    try:
        r = requests.get(MANIFEST_URL, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return None


def fetch_recipe(path):
    """Fetch a recipe .txt file by relative path (e.g. 'bolognase.txt' or 'DASH/grain bowl.txt')"""
    try:
        url = RECIPE_BASE + requests.utils.quote(path, safe='/')
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.text
    except Exception as e:
        return None


def recipe_to_html(raw, name):
    """Convert gastro recipe pseudocode to simple HTML 3.2."""
    lines = raw.splitlines()
    html = recipe_header(name)
    total = len(lines)
    pad = len(str(total))
    html += "<font face=\"Monaco\" size=\"3\">\n"
    for i, line in enumerate(lines, 1):
        # Escape HTML entities
        line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        # Preserve whitespace without <pre>
        line = line.replace('\t', '&#160;&#160;&#160;&#160;')
        line = line.replace(' ', '&#160;')
        # Right-aligned line number
        num = str(i).rjust(pad).replace(' ', '&#160;')
        html += f"{num}&#160;&#160;{line}<br>\n"
    html += "</font>\n"
    return html


def slug_to_path(slug, manifest):
    """
    slug is like 'bolognase' or 'DASH/grain_bowl'
    Returns the actual file path (with spaces) for fetching.
    """
    if '/' in slug:
        parts = slug.split('/', 1)
        folder = parts[0]
        file_slug = parts[1].replace('_', ' ')
        if folder in manifest.get('folders', {}):
            for fname in manifest['folders'][folder]:
                if fname.replace(' ', '_').replace('.txt', '') == parts[1].replace('.txt', ''):
                    return folder + '/' + fname
                # also try direct match after slug normalization
                normalized = re.sub(r'[^a-z0-9]', '_', fname.lower().replace('.txt', ''))
                query_norm = re.sub(r'[^a-z0-9]', '_', parts[1].lower())
                if normalized == query_norm:
                    return folder + '/' + fname
        return None
    else:
        file_slug = slug.replace('_', ' ')
        for fname in manifest.get('root', []):
            if fname.replace(' ', '_').replace('.txt', '') == slug.replace('.txt', ''):
                return fname
            normalized = re.sub(r'[^a-z0-9]', '_', fname.lower().replace('.txt', ''))
            query_norm = re.sub(r'[^a-z0-9]', '_', slug.lower())
            if normalized == query_norm:
                return fname
        return None


def make_page(title, body):
    # Hidden random comment ensures MacWeb sees unique content each load,
    # preventing cache and preserving the slow-render "animation" effect
    cache_bust = f"<!-- {random.randint(100000, 999999)} -->"
    return f"""<!DOCTYPE html>
<html>
<head><title>{title}</title>
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
</head>
<body>
{cache_bust}
{body}
</body>
</html>"""


def home_header():
    return (
        "<center>\n"
        "<h6><font size=\"7\" face=\"Times\"><b>GASTRONOMY</b></font><br>by Jordan Eunson</h6>\n"
        "<p><i>Recipes as pseudocode.</i></p>\n"
        "</center>\n"
        "<hr>\n"
    )


def recipe_header(recipe_name):
    return (
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"0\">\n"
        "<tr>\n"
        f"<td valign=\"bottom\"><h5><b><font size=\"5\" face=\"Times\">{recipe_name}</font></b></h5></td>\n"
        "<td align=\"right\" valign=\"middle\"><a href=\"/\">&#171; All Recipes</a></td>\n"
        "</tr>\n"
        "</table>\n"
        "<hr>\n"
    )


def listing_page(manifest):
    html = home_header()

    root = manifest.get('root', [])
    if root:
        html += "<b>Recipes:</b><br>\n<ul>\n"
        for fname in sorted(root):
            slug = re.sub(r'\.txt$', '', fname).replace(' ', '_')
            display = re.sub(r'\.txt$', '', fname).title()
            html += f'<li><a href="/recipe/{slug}">{display}</a></li>\n'
        html += "</ul>\n"

    folders = manifest.get('folders', {})
    for folder_name in sorted(folders.keys()):
        html += f"<hr>\n<b>{folder_name}:</b><br>\n<ul>\n"
        for fname in sorted(folders[folder_name]):
            slug = folder_name + '/' + re.sub(r'\.txt$', '', fname).replace(' ', '_')
            display = re.sub(r'\.txt$', '', fname).title()
            html += f'<li><a href="/recipe/{slug}">{display}</a></li>\n'
        html += "</ul>\n"

    return make_page("Gastronomy - Jordan Eunson", html)


NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
}


def handle_request(req):
    path = req.path.rstrip('/')

    if path == '' or path == '/':
        manifest = fetch_manifest()
        if manifest is None:
            return make_page("Error", "<p>Could not load recipe list. Try again later.</p>"), 500, NO_CACHE_HEADERS
        return listing_page(manifest), 200, NO_CACHE_HEADERS

    if path.startswith('/recipe/'):
        slug = path[len('/recipe/'):]
        manifest = fetch_manifest()
        if manifest is None:
            return make_page("Error", "<p>Could not load manifest.</p>"), 500, NO_CACHE_HEADERS

        file_path = slug_to_path(slug, manifest)
        if file_path is None:
            return make_page("Not Found", f"<p>Recipe not found: {slug}</p><p><a href='/'>Back</a></p>"), 404, NO_CACHE_HEADERS

        raw = fetch_recipe(file_path)
        if raw is None:
            return make_page("Error", f"<p>Could not load recipe file: {file_path}</p>"), 500, NO_CACHE_HEADERS

        display_name = re.sub(r'\.txt$', '', file_path.split('/')[-1]).title()
        body = recipe_to_html(raw, display_name)
        return make_page(display_name + " - Gastronomy", body), 200, NO_CACHE_HEADERS

    # Fallback: listing
    manifest = fetch_manifest()
    if manifest is None:
        return make_page("Error", "<p>Could not load recipe list.</p>"), 500, NO_CACHE_HEADERS
    return listing_page(manifest), 200, NO_CACHE_HEADERS
