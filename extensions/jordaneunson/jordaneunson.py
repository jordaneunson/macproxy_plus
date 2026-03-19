from flask import request
import requests
import json
import re

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
    html = f"<h3>{name}</h3>\n<hr>\n<pre>\n"
    for line in lines:
        # Escape HTML entities
        line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        html += line + "\n"
    html += "</pre>\n"
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
    return f"""<!DOCTYPE html>
<html>
<head><title>{title}</title></head>
<body>
{body}
</body>
</html>"""


def listing_page(manifest):
    html = "<h3>Gastronomy</h3>\n"
    html += "<p>Recipes as pseudocode. Jordan Eunson.</p>\n"
    html += "<hr>\n"

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

    html += '<hr>\n<a href="/">Home</a>\n'
    return make_page("Gastronomy - Jordan Eunson", html)


def handle_request(req):
    path = req.path.rstrip('/')

    if path == '' or path == '/':
        manifest = fetch_manifest()
        if manifest is None:
            return make_page("Error", "<p>Could not load recipe list. Try again later.</p>"), 500
        return listing_page(manifest), 200

    if path.startswith('/recipe/'):
        slug = path[len('/recipe/'):]
        manifest = fetch_manifest()
        if manifest is None:
            return make_page("Error", "<p>Could not load manifest.</p>"), 500

        file_path = slug_to_path(slug, manifest)
        if file_path is None:
            return make_page("Not Found", f"<p>Recipe not found: {slug}</p><p><a href='/'>Back</a></p>"), 404

        raw = fetch_recipe(file_path)
        if raw is None:
            return make_page("Error", f"<p>Could not load recipe file: {file_path}</p>"), 500

        display_name = re.sub(r'\.txt$', '', file_path.split('/')[-1]).title()
        body = recipe_to_html(raw, display_name)
        body += '<hr>\n<a href="/">Back to list</a>\n'
        return make_page(display_name + " - Gastronomy", body), 200

    # Fallback: listing
    manifest = fetch_manifest()
    if manifest is None:
        return make_page("Error", "<p>Could not load recipe list.</p>"), 500
    return listing_page(manifest), 200
