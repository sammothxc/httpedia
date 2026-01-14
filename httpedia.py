from flask import Flask, Response
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

WIKIPEDIA_BASE = 'https://en.wikipedia.org'

HEADERS = {
    'User-Agent': 'HTTPedia/1.0 (https://httpedia.samwarr.dev; minimal Wikipedia proxy for vintage browsers)'
}

DOCTYPE = '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 2.0//EN">'

META = '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'

PAGE_TEMPLATE = '''{doctype}
<html>
<head>
{meta}
<title>{title} - HTTPedia</title>
</head>
<body>
{header}
<center>
<h2>{title}</h2>
</center>
{content}
</body>
</html>'''

HEADER = '''<center>
<h1><a href="/">HTTPedia</a></h1>
<small>
Basic HTML Wikipedia proxy for retro computers. Built by 
<a href="https://github.com/sammothxc/httpedia" target="_blank">
<b>sammothxc</b></a>, 2026.
</small>
</center>
<hr>'''

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

@app.route('/wiki/<path:title>')
def wiki(title):
    try:
        resp = requests.get(f'{WIKIPEDIA_BASE}/wiki/{title}', headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        return Response(render_error(f'Could not fetch article: {e}'), mimetype='text/html')

    soup = BeautifulSoup(resp.text, 'html.parser')

    page_title = soup.find('h1', {'id': 'firstHeading'})
    title_text = page_title.get_text() if page_title else title.replace('_', ' ')

    content = soup.find('div', {'class': 'mw-parser-output'})
    if not content:
        return Response(render_error('Could not parse article'), mimetype='text/html')

    unwanted_selectors = [
        'script', 'style', 'img', 'figure', 'table',
        '.infobox', '.navbox', '.sidebar', '.mw-editsection',
        '.reference', '.reflist', '.thumb', '.mw-empty-elt',
        '.noprint', '.mw-jump-link', '.toc', '#coordinates',
        '.hatnote', '.shortdescription', '.mbox-small'
    ]

    for selector in unwanted_selectors:
        for tag in content.select(selector):
            tag.decompose()

    for sup in content.find_all('sup', {'class': 'reference'}):
        sup.decompose()

    body_content = process_content(content)
    
    return Response(render_page(title_text, body_content), mimetype='text/html')

def render_page(title, content):
    return PAGE_TEMPLATE.format(
        doctype=DOCTYPE,
        meta=META,
        title=title,
        header=HEADER.format(title=title),
        content=content,
    )

def render_error(message):
    return ERROR_TEMPLATE.format(
        doctype=DOCTYPE,
        meta=META,
        message=message
    )

def process_content(content):
    lines = []
    for element in content.children:
        if element.name == 'p':
            html = process_paragraph(element)
            if html.strip():
                lines.append(f'<p>{html}</p>')

        elif element.name in ['h2', 'h3', 'h4']:
            text = clean_text(element.get_text())
            text = re.sub(r'\[edit\]', '', text).strip()
            if text:
                lines.append(f'<{element.name}>{text}</{element.name}>')

        elif element.name == 'ul':
            lines.append(process_list(element))

        elif element.name == 'ol':
            lines.append(process_list(element, ordered=True))

        elif element.name == 'dl':
            for child in element.children:
                if child.name == 'dt':
                    lines.append(f'<p><b>{clean_text(child.get_text())}</b></p>')
                elif child.name == 'dd':
                    lines.append(f'<p>{clean_text(child.get_text())}</p>')

    return '\n'.join(lines)


def process_paragraph(element):
    result = []
    
    for child in element.children:
        if child.name == 'a':
            href = child.get('href', '')
            text = child.get_text()
            
            if not text.strip():
                continue
            
            if href.startswith('/wiki/') and ':' not in href:
                result.append(f'<a href="{href}">{text}</a>')
            else:
                result.append(text)
        
        elif child.string:
            result.append(re.sub(r'\s+', ' ', child.string))
        
        elif hasattr(child, 'get_text'):
            result.append(re.sub(r'\s+', ' ', child.get_text()))
    
    text = ''.join(result)
    text = re.sub(r'\[edit\]', '', text)
    text = re.sub(r'\[\d+\]', '', text)
    text = re.sub(r'\[citation needed\]', '', text)
    return text.strip()


def process_list(element, ordered=False):
    items = []
    for li in element.find_all('li', recursive=False):
        html = process_paragraph(li)
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
    app.run(host='0.0.0.0', port=8080, debug=True)