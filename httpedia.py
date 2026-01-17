import os
import requests
import re
from flask import Flask, Response, request, redirect, send_file
from bs4 import BeautifulSoup
from dotenv import load_dotenv


load_dotenv()
app = Flask(__name__)


DEFAULTS = {
    'skin': 'light',
    'img': '1',
}


WIKIPEDIA_BASE = 'https://en.wikipedia.org'


HEADERS = {
    'User-Agent': 'HTTPedia/1.0 (https://httpedia.samwarr.dev; minimal Wikipedia proxy for vintage browsers)'
}


DOCTYPE = '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 2.0//EN">'


META = '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'


BODY_STYLES = {
    'light': 'bgcolor="#ffffff" text="#000000" link="#0000ee" vlink="#551a8b"',
    'dark': 'bgcolor="#1a1a1a" text="#e0e0e0" link="#6db3f2" vlink="#a0a0ff"'
}


HOME_TEMPLATE = '''{doctype}
<html>
<head>
{meta}
<title>HTTPedia - Wikipedia for Retro Computers</title>
</head>
<body {body_style}>
<center>
<small>
<a href="/?{skin_toggle_params}">{skin_toggle_text}</a> | 
<a href="/?{img_toggle_params}">{img_toggle_text}</a> | 
<a href="https://ko-fi.com/sammothxc" target="_blank">Keep it running</a>
</small>
<hr>
<br>
{logo}
<small>
Basic HTML Wikipedia proxy for retro computers. Built by 
<a href="https://github.com/sammothxc/httpedia" target="_blank">
<b>sammothxc</b></a>, 2026.
</small>
<br>
<br>
<form action="/search" method="get">
<input type="text" name="q" size="30">
<input type="hidden" name="skin" value="{skin}">
<input type="hidden" name="img" value="{img}">
<input type="submit" value="Search">
</form>
<br>
<h3>Popular Links</h3>
<p>
<a href="/wiki/Computer?{prefs}">Computer</a> | 
<a href="/wiki/Internet?{prefs}">Internet</a> | 
<a href="/wiki/World_Wide_Web?{prefs}">World Wide Web</a> | 
<a href="/wiki/Compaq_Portable?{prefs}">Compaq Portable</a> | 
<a href="/wiki/IBM_PC?{prefs}">IBM PC</a> | 
<a href="/wiki/Apple_II?{prefs}">Apple II</a>
</p>
<h3>Other Retro-Friendly Sites</h3>
<p>
<a href="http://frogfind.com" target="_blank">FrogFind</a> | 
<a href="http://68k.news" target="_blank">68k.news</a> | 
<a href="http://textfiles.com/" target="_blank">textfiles.com</a>*
</p>
</center>
</body>
</html>'''


PAGE_TEMPLATE = '''{doctype}
<html>
<head>
{meta}
<title>{title} - HTTPedia</title>
</head>
<body {body_style}>
{header}
{content}
{footer}
</body>
</html>'''


HEADER = '''<center>
<h1>HTTPedia</h1>
<small>
Basic HTML Wikipedia proxy for retro computers. Built by 
<a href="https://github.com/sammothxc/httpedia" target="_blank">
<b>sammothxc</b></a>, 2026.
</small>
<hr>
<small><a href="/?{prefs}">Home/Search</a> | 
<a href="/wiki/{title_slug}?{skin_toggle_params}">{skin_toggle_text}</a> | 
<a href="/wiki/{title_slug}?{img_toggle_params}">{img_toggle_text}</a> | 
<a href="https://ko-fi.com/sammothxc" target="_blank">Keep it running</a>
</small>
</center>
<hr>'''


FOOTER = '''<hr>
<center>
<small>
Content sourced from <a href="{wikipedia_url}" target="_blank">this Wikipedia page</a> under 
<a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank">CC BY-SA 4.0</a>.
Donations support HTTPedia hosting, not Wikipedia.
</small>
<br>
</center>'''


ERROR_TEMPLATE = '''{doctype}
<html>
<head>
{meta}
<title>Error - HTTPedia</title>
</head>
<body>
<h1>Error</h1>
<p>{message}</p>
<p><a href="/">Home</a></p>
</body>
</html>'''


def get_prefs():
    skin = request.args.get('skin', 'light')
    img = request.args.get('img', '1')
    # planned prefs:
    # lang = request.args.get('lang', 'en')
    return {'skin': skin, 'img': img}


def build_prefs_string(prefs):
    non_default = {k: v for k, v in prefs.items() if v != DEFAULTS.get(k)}
    if not non_default:
        return ''
    return '&'.join(f'{k}={v}' for k, v in non_default.items())


def get_skin_toggle(prefs):
    new_prefs = prefs.copy()
    if prefs['skin'] == 'light':
        new_prefs['skin'] = 'dark'
        text = 'Dark Mode'
    else:
        new_prefs['skin'] = 'light'
        text = 'Light Mode'
    return build_prefs_string(new_prefs), text


def get_img_toggle(prefs):
    new_prefs = prefs.copy()
    if prefs['img'] == '0':
        new_prefs['img'] = '1'
        text = 'Load Images'
    else:
        new_prefs['img'] = '0'
        text = "Don't Load Images"
    return build_prefs_string(new_prefs), text


@app.route('/')
def home():
    prefs = get_prefs()
    skin = prefs['skin']
    img = prefs['img']
    prefs_string = build_prefs_string(prefs)
    skin_toggle_params, skin_toggle_text = get_skin_toggle(prefs)
    img_toggle_params, img_toggle_text = get_img_toggle(prefs)

    if img == '1':
        logo = '<img src="/static/httpedia-logo.gif" alt="HTTPedia Logo" width="323" height="65"><br>'
    else:
        logo = '<h1>HTTPedia</h1>'

    return HOME_TEMPLATE.format(
        doctype=DOCTYPE,
        meta=META,
        body_style=BODY_STYLES.get(skin, BODY_STYLES['light']),
        skin=skin,
        img=img,
        prefs=prefs_string,
        skin_toggle_params=skin_toggle_params,
        skin_toggle_text=skin_toggle_text,
        img_toggle_params=img_toggle_params,
        img_toggle_text=img_toggle_text,
        logo=logo,
        footer=FOOTER.format(
            wikipedia_url=WIKIPEDIA_BASE
        )
    )


@app.route('/search')
def search():
    prefs = get_prefs()
    query = request.args.get('q', '')
    if not query:
        prefs_string = build_prefs_string(prefs)
        return redirect(f'/?{prefs_string}' if prefs_string else '/')
    
    prefs_string = build_prefs_string(prefs)
    skin = prefs['skin']
    skin_toggle_params, skin_toggle_text = get_skin_toggle(prefs)
    img_toggle_params, img_toggle_text = get_img_toggle(prefs)
    
    results = search_wikipedia(query)
    wikipedia_url = f'{WIKIPEDIA_BASE}/wiki/Special:Search?search={query}'
    title_text = f'Search: {query}'

    if not results:
        results_html = '<p>No results found.</p>'
    else:
        results_html = f'<center><p>Search Results for <strong>"{query}"</strong></p></center><ul>\n'
        for r in results:
            title_slug = r['title'].replace(' ', '_')
            url = f'/wiki/{title_slug}?{prefs_string}' if prefs_string else f'/wiki/{title_slug}'
            snippet = r['snippet'] if r['snippet'] else 'No description available.'
            results_html += f'<li><a href="{url}">{r["title"]}</a> - {snippet}</li>\n'
        results_html += '</ul>'
    
    return Response(render_page(
        title_text, 
        results_html, 
        wikipedia_url, 
        skin, 
        query, 
        prefs_string, 
        skin_toggle_params, 
        skin_toggle_text, 
        img_toggle_params, 
        img_toggle_text
    ), mimetype='text/html')

def search_wikipedia(query, limit=10):
    try:
        resp = requests.get(
            f'{WIKIPEDIA_BASE}/w/api.php',
            params={
                'action': 'opensearch',
                'search': query,
                'limit': limit,
                'format': 'json'
            },
            headers=HEADERS,
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        
        # opensearch returns: [query, [titles], [descriptions], [urls]]
        titles = data[1] if len(data) > 1 else []
        descriptions = data[2] if len(data) > 2 else []
        
        results = []
        for i, title in enumerate(titles):
            results.append({
                'title': title,
                'snippet': descriptions[i] if i < len(descriptions) else ''
            })
        return results
    except:
        return []


@app.route('/wiki/<path:title>')
def wiki(title):
    prefs = get_prefs()
    return fetch_and_render(title, prefs)


def fetch_and_render(title, prefs):
    skin = prefs['skin']
    prefs_string = build_prefs_string(prefs)
    skin_toggle_params, skin_toggle_text = get_skin_toggle(prefs)
    img_toggle_params, img_toggle_text = get_img_toggle(prefs)

    try:
        resp = requests.get(f'{WIKIPEDIA_BASE}/wiki/{title}', headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        return Response(render_error(f'Could not fetch article: {e}'), mimetype='text/html')

    soup = BeautifulSoup(resp.text, 'lxml')

    page_title = soup.find('h1', {'id': 'firstHeading'})
    title_text = page_title.get_text() if page_title else title.replace('_', ' ')

    all_outputs = soup.find_all('div', {'class': 'mw-parser-output'})
    content = max(all_outputs, key=lambda div: len(list(div.children))) if all_outputs else None
    if not content:
        return Response(render_error('Could not parse article'), mimetype='text/html')
    
    unwanted_selectors = [
        'script', 'style', 'img', 'figure', 'table',
        '.infobox', '.navbox', '.sidebar', '.mw-editsection',
        '.reference', '.reflist', '.thumb', '.mw-empty-elt',
        '.noprint', '.mw-jump-link', '.toc', '#coordinates',
        '.hatnote', '.shortdescription', '.mbox-small',
        '.ambox', '.cmbox', '.fmbox', '.imbox', '.ombox', '.tmbox',
        '.portal', '.sistersitebox', '.noexcerpt',
        '.mw-references-wrap', '.refbegin', '.refend',
        '.navbox-styles', '.catlinks', '.mw-authority-control',
    ]

    for selector in unwanted_selectors:
        for tag in content.select(selector):
            tag.decompose()

    for sup in content.find_all('sup', {'class': 'reference'}):
        sup.decompose()

    body_content = f'<center><h2>{title}</h2></center>'
    body_content += process_content(content, prefs_string)
    wikipedia_url = f'{WIKIPEDIA_BASE}/wiki/{title}'

    return Response(render_page(
        title_text, 
        body_content, 
        wikipedia_url, 
        skin, 
        title, 
        prefs_string, 
        skin_toggle_params, 
        skin_toggle_text, 
        img_toggle_params, 
        img_toggle_text
    ), mimetype='text/html')


def render_page(title, content, wikipedia_url, skin, title_slug, prefs, skin_toggle_params, skin_toggle_text, img_toggle_params, img_toggle_text):
    return PAGE_TEMPLATE.format(
        doctype=DOCTYPE,
        meta=META,
        title=title,
        body_style=BODY_STYLES.get(skin, BODY_STYLES['light']),
        header=HEADER.format(
            title_slug=title_slug,
            prefs=prefs,
            skin_toggle_params=skin_toggle_params,
            skin_toggle_text=skin_toggle_text,
            img_toggle_params=img_toggle_params,
            img_toggle_text=img_toggle_text,
        ),
        content=content,
        footer=FOOTER.format(
            wikipedia_url=wikipedia_url
        ),
    )


def render_error(message):
    return ERROR_TEMPLATE.format(
        doctype=DOCTYPE,
        meta=META,
        message=message
    )


def process_content(content, prefs):
    lines = []
    process_element(content, lines, prefs)
    return '\n'.join(lines)


def process_element(element, lines, prefs):
    for child in element.children:
        if child.name == 'p':
            html = process_paragraph(child, prefs)
            if html.strip():
                lines.append(f'<p>{html}</p>')

        elif child.name in ['h2', 'h3', 'h4', 'h5', 'h6']:
            text = clean_text(child.get_text())
            text = re.sub(r'\[edit\]', '', text).strip()
            if text:
                lines.append(f'<{child.name}>{text}</{child.name}>')

        elif child.name == 'ul':
            list_html = process_list(child, ordered=False, prefs=prefs)
            if list_html:
                lines.append(list_html)

        elif child.name == 'ol':
            list_html = process_list(child, ordered=True, prefs=prefs)
            if list_html:
                lines.append(list_html)

        elif child.name == 'dl':
            for item in child.children:
                if item.name == 'dt':
                    lines.append(f'<p><b>{clean_text(item.get_text())}</b></p>')
                elif item.name == 'dd':
                    html = process_paragraph(item, prefs)
                    if html.strip():
                        lines.append(f'<p>{html}</p>')

        elif child.name == 'blockquote':
            text = clean_text(child.get_text())
            if text.strip():
                lines.append(f'<blockquote>{text}</blockquote>')

        elif child.name == 'div':
            if 'mw-heading' in child.get('class', []):
                for h in child.find_all(['h2', 'h3', 'h4', 'h5', 'h6'], recursive=False):
                    text = clean_text(h.get_text())
                    text = re.sub(r'\[edit\]', '', text).strip()
                    if text:
                        lines.append(f'<{h.name}>{text}</{h.name}>')
            else:
                process_element(child, lines, prefs)

        elif child.name == 'section':
            process_element(child, lines, prefs)


def process_paragraph(element, prefs):
    result = []
    
    for child in element.children:
        if child.name == 'a':
            href = child.get('href', '')
            text = child.get_text()
            
            if not text.strip():
                continue
            
            if href.startswith('/wiki/') and ':' not in href:
                if prefs:
                    result.append(f'<a href="{href}?{prefs}">{text}</a>')
                else:
                    result.append(f'<a href="{href}">{text}</a>')
        
        elif child.name == 'b' or child.name == 'strong':
            text = child.get_text()
            if text.strip():
                result.append(text)
        
        elif child.name == 'i' or child.name == 'em':
            text = child.get_text()
            if text.strip():
                result.append(f'<i>{text}</i>')
        
        elif child.name == 'br':
            result.append('<br>')
        
        elif child.name in ['span', 'small', 'sup', 'sub']:
            result.append(process_paragraph(child, prefs))
        
        elif child.string:
            result.append(re.sub(r'\s+', ' ', child.string))
        
        elif hasattr(child, 'get_text'):
            result.append(re.sub(r'\s+', ' ', child.get_text()))
    
    text = ''.join(result)
    text = re.sub(r'\[edit\]', '', text)
    text = re.sub(r'\[\d+\]', '', text)
    text = re.sub(r'\[citation needed\]', '', text)
    return text.strip()


def process_list(element, ordered=False, prefs=''):
    items = []
    for li in element.find_all('li', recursive=False):
        html = process_paragraph(li, prefs)
        if html.strip():
            items.append(f'<li>{html}</li>')

    if not items:
        return ''

    tag = 'ol' if ordered else 'ul'
    return f'<{tag}>\n' + '\n'.join(items) + f'\n</{tag}>'


def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\[edit\]', '', text)
    text = re.sub(r'\[\d+\]', '', text)
    text = re.sub(r'\[citation needed\]', '', text)
    return text.strip()


if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=80, debug=debug)