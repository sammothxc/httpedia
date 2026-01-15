import os
import requests
import re
from flask import Flask, Response, request, redirect
from bs4 import BeautifulSoup
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

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
<a href="{skin_toggle_url}">{skin_toggle_text}</a> | 
<a href="https://ko-fi.com/sammothxc" target="_blank">Keep it running</a>
</small>
<hr>
<br>
<h1>HTTPedia</h1>
<!--<img src="./logo.gif" alt="HTTPedia Logo" width="128" height="128"> -->
<small>
Basic HTML Wikipedia proxy for retro computers. Built by 
<a href="https://github.com/sammothxc/httpedia" target="_blank">
<b>sammothxc</b></a>, 2026.
</small>
<br>
<br>
<form action="{search_action}" method="get">
<input type="text" name="q" size="30">
<input type="submit" value="Search">
</form>
<br>
<h3>Quick Links</h3>
<p>
<a href="{prefix}/wiki/Computer">Computer</a> | 
<a href="{prefix}/wiki/Internet">Internet</a> | 
<a href="{prefix}/wiki/World_Wide_Web">World Wide Web</a>
<a href="{prefix}/wiki/Compaq_Portable">Compaq Portable</a> | 
<a href="{prefix}/wiki/IBM_PC">IBM PC</a> | 
<a href="{prefix}/wiki/Apple_II">Apple II</a>
</p>
<h3>Other Retro-Friendly Sites</h3>
<p>
<a href="http://frogfind.com">FrogFind</a> | 
<a href="http://68k.news">68k.news</a> <!-- | 
<!-- <a href="http://textfiles.com">textfiles.com</a> -->
</p>
</center>
{footer}
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
<center>
<h2>{title}</h2>
</center>
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
<p><a href="{home_url}">Home/Search</a> | <a href="{wikipedia_url}" target="_blank">View on Wikipedia</a> | {skin_toggle} | <a href="https://ko-fi.com/sammothxc" target="_blank">Keep it running</a></p>
</center>
<hr>'''

FOOTER = '''<hr>
<center>
<small>
Content sourced from <a href="https://en.wikipedia.org" target="_blank">Wikipedia</a> under <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank">CC BY-SA 4.0</a>.
</small>
<br>
<small>
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

@app.route('/')
def home_light():
    return render_home(skin='light')

@app.route('/dark/')
def home_dark():
    return render_home(skin='dark')

def render_home(skin='light'):
    if skin == 'light':
        prefix = ''
        search_action = '/search'
        skin_toggle_url = '/dark/'
        skin_toggle_text = 'Dark Mode'
    else:
        prefix = '/dark'
        search_action = '/dark/search'
        skin_toggle_url = '/'
        skin_toggle_text = 'Light Mode'
    
    return HOME_TEMPLATE.format(
        doctype=DOCTYPE,
        meta=META,
        body_style=BODY_STYLES.get(skin, BODY_STYLES['light']),
        prefix=prefix,
        search_action=search_action,
        skin_toggle_url=skin_toggle_url,
        skin_toggle_text=skin_toggle_text,
        footer=FOOTER,
    )

@app.route('/search')
def search_light():
    return handle_search(skin='light')

@app.route('/dark/search')
def search_dark():
    return handle_search(skin='dark')

def handle_search(skin='light'):
    query = request.args.get('q', '')
    if not query:
        return render_home(skin)
    # For now, just redirect to the wiki page
    # We'll add real search in Phase 2
    title = query.replace(' ', '_')
    if skin == 'dark':
        return redirect(f'/dark/wiki/{title}')
    return redirect(f'/wiki/{title}')

@app.route('/wiki/<path:title>')
def wiki_light(title):
    return fetch_and_render(title, skin='light')

@app.route('/dark/wiki/<path:title>')
def wiki_dark(title):
    return fetch_and_render(title, skin='dark')

def fetch_and_render(title, skin='light'):
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

    body_content = process_content(content, skin)
    wikipedia_url = f'{WIKIPEDIA_BASE}/wiki/{title}'

    return Response(render_page(title_text, body_content, wikipedia_url, skin, title), mimetype='text/html')

def render_page(title, content, wikipedia_url='', skin='light', title_slug=''):
    if skin == 'light':
        skin_toggle = f'<a href="/dark/wiki/{title_slug}">Dark Mode</a>'
        home_url = '/'
    else:
        skin_toggle = f'<a href="/wiki/{title_slug}">Light Mode</a>'
        home_url = '/dark/'
    
    return PAGE_TEMPLATE.format(
        doctype=DOCTYPE,
        meta=META,
        title=title,
        body_style=BODY_STYLES.get(skin, BODY_STYLES['light']),
        header=HEADER.format(wikipedia_url=wikipedia_url, skin_toggle=skin_toggle, home_url=home_url),
        content=content,
        footer=FOOTER,
    )


def render_error(message):
    return ERROR_TEMPLATE.format(
        doctype=DOCTYPE,
        meta=META,
        message=message
    )

def process_content(content, skin='light'):
    lines = []
    process_element(content, lines, skin)
    return '\n'.join(lines)



def process_element(element, lines, skin='light'):
    for child in element.children:
        if child.name == 'p':
            html = process_paragraph(child, skin)
            if html.strip():
                lines.append(f'<p>{html}</p>')

        elif child.name in ['h2', 'h3', 'h4', 'h5', 'h6']:
            text = clean_text(child.get_text())
            text = re.sub(r'\[edit\]', '', text).strip()
            if text:
                lines.append(f'<{child.name}>{text}</{child.name}>')

        elif child.name == 'ul':
            list_html = process_list(child, ordered=False, skin=skin)
            if list_html:
                lines.append(list_html)

        elif child.name == 'ol':
            list_html = process_list(child, ordered=True, skin=skin)
            if list_html:
                lines.append(list_html)

        elif child.name == 'dl':
            for item in child.children:
                if item.name == 'dt':
                    lines.append(f'<p><b>{clean_text(item.get_text())}</b></p>')
                elif item.name == 'dd':
                    html = process_paragraph(item)
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
                process_element(child, lines, skin)

        elif child.name == 'section':
            process_element(child, lines, skin)

def process_paragraph(element, skin='light'):
    result = []
    
    for child in element.children:
        if child.name == 'a':
            href = child.get('href', '')
            text = child.get_text()
            
            if not text.strip():
                continue
            
            if href.startswith('/wiki/') and ':' not in href:
                if skin == 'dark':
                    href = '/dark' + href
                result.append(f'<a href="{href}">{text}</a>')
            else:
                result.append(text)
        
        elif child.name == 'b' or child.name == 'strong':
            text = child.get_text()
            if text.strip():
                result.append(f'<b>{text}</b>')
        
        elif child.name == 'i' or child.name == 'em':
            text = child.get_text()
            if text.strip():
                result.append(f'<i>{text}</i>')
        
        elif child.name == 'br':
            result.append('<br>')
        
        elif child.name in ['span', 'small', 'sup', 'sub']:
            result.append(process_paragraph(child, skin))
        
        elif child.string:
            result.append(re.sub(r'\s+', ' ', child.string))
        
        elif hasattr(child, 'get_text'):
            result.append(re.sub(r'\s+', ' ', child.get_text()))
    
    text = ''.join(result)
    text = re.sub(r'\[edit\]', '', text)
    text = re.sub(r'\[\d+\]', '', text)
    text = re.sub(r'\[citation needed\]', '', text)
    return text.strip()


def process_list(element, ordered=False, skin='light'):
    items = []
    for li in element.find_all('li', recursive=False):
        html = process_paragraph(li, skin)
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
    app.run(host='0.0.0.0', port=8080, debug=debug)