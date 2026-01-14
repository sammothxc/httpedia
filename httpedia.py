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

    soup = BeautifulSoup(resp.text, 'lxml')

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
    process_element(content, lines)
    return '\n'.join(lines)


def process_element(element, lines):
    for child in element.children:
        if child.name == 'p':
            html = process_paragraph(child)
            if html.strip():
                lines.append(f'<p>{html}</p>')

        elif child.name in ['h2', 'h3', 'h4', 'h5', 'h6']:
            text = clean_text(child.get_text())
            text = re.sub(r'\[edit\]', '', text).strip()
            if text:
                lines.append(f'<{child.name}>{text}</{child.name}>')

        elif child.name == 'ul':
            list_html = process_list(child)
            if list_html:
                lines.append(list_html)

        elif child.name == 'ol':
            list_html = process_list(child, ordered=True)
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
                process_element(child, lines)

        elif child.name == 'section':
            process_element(child, lines)

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
            result.append(process_paragraph(child))
        
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