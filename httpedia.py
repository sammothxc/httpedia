import os
import requests
import re
import logging
from logging.handlers import RotatingFileHandler
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import Flask, Response, request, redirect
from markupsafe import escape
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO


LOG_DIR = '/var/log/httpedia'


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


HEADER = '''<center>
<h1>HTTPedia</h1>
<small>
Basic HTML Wikipedia proxy for retro computers. Built by 
<a href="https://github.com/sammothxc/httpedia" target="_blank">
<b>sammothxc</b></a>, 2026.
</small>
<hr>
<small><a href="/?{prefs_string}">Home/Search</a> | 
<a href={skin_toggle}</a> | 
<a href={img_toggle}</a> | 
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
<input type="text" name="{input_name}" size="30">
<input type="submit" value="Search">
</form>
<br>
<a href="/about?{prefs_string}">What is HTTPedia?</a>
<br><br>
<hr>
<h3>Popular Links</h3>
<p>
{popular_links}
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

ABOUT_TEMPLATE = '''{doctype}
<html>
<head>
{meta}
<title>About HTTPedia</title>
</head>
<body {body_style}>
{header}
{content}
</body>
</html>'''

PAGE_TEMPLATE = '''{doctype}
<html>
<head>
{meta}
<title>{title_text} - HTTPedia</title>
</head>
<body {body_style}>
{header}
{content}
{footer}
</body>
</html>'''


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


if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

file_handler = RotatingFileHandler(
    f'{LOG_DIR}/access.log',
    maxBytes=1024*1024,
    backupCount=5
)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
file_handler.setLevel(logging.INFO)

access_logger = logging.getLogger('httpedia.access')
access_logger.setLevel(logging.INFO)
access_logger.addHandler(file_handler)

load_dotenv()

app = Flask(__name__)

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1 per second"]
)
limiter.init_app(app)

Image.MAX_IMAGE_PIXELS = 10000000


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

    input_name = 'q'
    if skin == 'dark':
        input_name += '_dark'
    if img == '0':
        input_name += '_noimg'

    def build_link(path, text):
        url = f'{path}?{prefs_string}' if prefs_string else path
        return f'<a href="{url}">{text}</a>'

    # implement actual popular links later on
    popular_links = [
        build_link('/wiki/Computer', 'Computer'),
        build_link('/wiki/Internet', 'Internet'),
        build_link('/wiki/World_Wide_Web', 'World Wide Web'),
        build_link('/wiki/Compaq_Portable', 'Compaq Portable'),
        build_link('/wiki/IBM_PC', 'IBM PC'),
        build_link('/wiki/Apple_II', 'Apple II'),
    ]

    return HOME_TEMPLATE.format(
        doctype=DOCTYPE,
        meta=META,
        body_style=BODY_STYLES.get(skin, BODY_STYLES['light']),
        prefs_string=prefs_string,
        skin_toggle_params=skin_toggle_params,
        skin_toggle_text=skin_toggle_text,
        img_toggle_params=img_toggle_params,
        img_toggle_text=img_toggle_text,
        logo=logo,
        input_name=input_name,
        popular_links=' | \n'.join(popular_links)
    )


@app.route('/search')
def search():
    query = None
    skin = 'light'
    img = '1'
    
    # i am proud of the workaround for not being able to use input type="hidden" in Microweb
    if request.args.get('q_dark_noimg') is not None:
        query = request.args.get('q_dark_noimg')
        skin = 'dark'
        img = '0'
    elif request.args.get('q_dark') is not None:
        query = request.args.get('q_dark')
        skin = 'dark'
        img = '1'
    elif request.args.get('q_noimg') is not None:
        query = request.args.get('q_noimg')
        skin = 'light'
        img = '0'
    elif request.args.get('q') is not None:
        query = request.args.get('q')
        skin = 'light'
        img = '1'
    
    if request.args.get('skin'):
        skin = request.args.get('skin')
    if request.args.get('img'):
        img = request.args.get('img')
    
    prefs = {'skin': skin, 'img': img}
    
    if not query:
        prefs_string = build_prefs_string(prefs)
        return redirect(f'/?{prefs_string}' if prefs_string else '/')
    
    prefs_string = build_prefs_string(prefs)
    skin_toggle_params, skin_toggle_text = get_skin_toggle(prefs)
    img_toggle_params, img_toggle_text = get_img_toggle(prefs)
    skin_toggle = f'/search?{skin_toggle_params}&q={query}' if prefs_string else f'/search?skin={("dark" if skin=="light" else "light")}&q={query}'
    img_toggle = f'/search?{img_toggle_params}&q={query}' if prefs_string else f'/search?img={("1" if img=="0" else "0")}&q={query}'
    
    results = search_wikipedia(query)
    wikipedia_url = f'{WIKIPEDIA_BASE}/wiki/Special:Search?search={query}'
    title_text = f'Search: {query}'

    if not results:
        content = '<p>No results found.</p>'
    else:
        content = f'<center><p>Search Results for <b>{escape(query)}</b></p></center><ul>\n'
        for r in results:
            title_slug = r['title'].replace(' ', '_')
            url = f'/wiki/{title_slug}?{prefs_string}' if prefs_string else f'/wiki/{title_slug}'
            snippet = r['snippet'] if r['snippet'] else 'No description available.'
            content += f'<li><a href="{url}">{r["title"]}</a> - {snippet}</li>\n'
        content += '</ul>'

    return PAGE_TEMPLATE.format(
        doctype=DOCTYPE,
        meta=META,
        title_text=title_text,
        body_style=BODY_STYLES.get(skin, BODY_STYLES['light']),
        header=HEADER.format(
            path='search?' + query, # x
            prefs_string=prefs_string,
            skin_toggle=skin_toggle,
            img_toggle=img_toggle,
        ),
        content=content,
        footer=FOOTER.format(
            wikipedia_url=wikipedia_url
        ),
    )


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
    skin = prefs['skin']
    img_enabled = prefs['img'] == '1'
    prefs_string = build_prefs_string(prefs)
    skin_toggle = f'/wiki/{title}?{get_skin_toggle(prefs)[0]}' if prefs_string else f'/wiki/{title}?skin={("dark" if skin=="light" else "light")}'
    img_toggle = f'/wiki/{title}?{get_img_toggle(prefs)[0]}' if prefs_string else f'/wiki/{title}?img={("1" if img_enabled==False else "0")}'

    try:
        resp = requests.get(f'{WIKIPEDIA_BASE}/wiki/{title}', headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        app.logger.error(f'Could not fetch article {title}: {e}')
        return Response(render_error('Could not fetch article. Please try again.'), mimetype='text/html')

    soup = BeautifulSoup(resp.text, 'lxml')

    page_title = soup.find('h1', {'id': 'firstHeading'})
    title_text = page_title.get_text() if page_title else title.replace('_', ' ')

    all_outputs = soup.find_all('div', {'class': 'mw-parser-output'})
    content = max(all_outputs, key=lambda div: len(list(div.children))) if all_outputs else None
    if not content:
        return Response(render_error('Could not parse article'), mimetype='text/html')
    
    article_image = ''
    if img_enabled:
        first_img = content.find('img', src=True)
        if first_img:
            src = first_img.get('src', '')
            if 'upload.wikimedia.org' in src:
                if '/commons/' in src:
                    img_path = src.split('/commons/')[-1]
                    article_image = f'<center><img src="/img/{img_path}" alt="{escape(title_text)}"></center><br>'
                elif '/en/' in src:
                    img_path = src.split('/en/')[-1]
                    article_image = f'<center><img src="/img/en/{img_path}" alt="{escape(title_text)}"></center><br>'
    
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

    body_content = f'<center><h2>{escape(title_text)}</h2></center>'
    body_content += article_image
    body_content += process_content(content, prefs_string)
    wikipedia_url = f'{WIKIPEDIA_BASE}/wiki/{title}'

    return PAGE_TEMPLATE.format(
        doctype=DOCTYPE,
        meta=META,
        title_text=title_text,
        body_style=BODY_STYLES.get(skin, BODY_STYLES['light']),
        header=HEADER.format(
            prefs_string=prefs_string,
            skin_toggle=skin_toggle,
            img_toggle=img_toggle,
        ),
        content=body_content,
        footer=FOOTER.format(
            wikipedia_url=wikipedia_url
        ),
    )


@app.route('/img/<path:image_path>')
@limiter.limit("1 per 5 seconds") # for now
def proxy_image(image_path):
    prefs = get_prefs()
    if prefs['img'] == '0':
        return Response(b'GIF89a\x01\x00\x01\x00\x00\x00\x00!', mimetype='image/gif')
    
    if not re.match(r'^[a-zA-Z0-9/_.-]+$', image_path):
        return Response(b'', status=400)
    
    if '..' in image_path:
        return Response(b'', status=400)
    
    image_url = f'https://upload.wikimedia.org/wikipedia/commons/{image_path}'
    
    gif_data = fetch_and_convert_image(image_url)
    if gif_data:
        return Response(gif_data, mimetype='image/gif')
    else:
        return Response(b'', status=404)


@app.route('/about')
def about():
    prefs = get_prefs()
    skin = prefs['skin']
    prefs_string = build_prefs_string(prefs)
    skin_toggle = f'"/about?{get_skin_toggle(prefs)[0]}">' if prefs_string else f'/about?skin={("dark" if skin=="light" else "light")}'
    img_toggle = f'/about?{get_img_toggle(prefs)[0]}' if prefs_string else f'/about?img={("1" if img_enabled==False else "0")}'

    content = '''
<h2>What is HTTPedia?</h2>
<p>HTTPedia is a lightweight Wikipedia proxy designed for vintage computers and retro web browsers
that can no longer use the modern web.</p>

<p>Modern Wikipedia is filled JavaScript, complex CSS, high-resolution images, and it makes use of lots of 
modern browser features that old machines can't handle. HTTPedia strips all that away and serves clean HTML 2.0 that works 
on browsers from the 1990s and earlier. In addition to cutting down on complexity, HTTPedia is served over HTTP meaning 
there are no minimum HTTPS or TLS requirements.</p>

<h3>Features</h3>
<p>
- Pure HTML 2.0 output (no JavaScript or CSS)<br>
- Images converted to small GIFs<br>
- Light and dark modes<br>
- Option to disable images entirely<br>
- Works on Netscape, Mosaic, early IE, and text browsers, even Microweb on an 8088!
</p>

<h3>So... Why?</h3>
<p>Because old computers deserve to access information too!</p>
<p>
Want to help out? 
<a href="https://github.com/sammothxc/httpedia" target="_blank">Leave feedback on the project on GitHub</a>
or 
<a href="https://ko-fi.com/sammothxc" target="_blank">donate to keep the server running.</a>
</p>
'''

    return ABOUT_TEMPLATE.format(
        doctype=DOCTYPE,
        meta=META,
        body_style=BODY_STYLES.get(skin, BODY_STYLES['light']),
        header=HEADER.format(
            prefs_string=prefs_string,
            skin_toggle=skin_toggle,
            img_toggle=img_toggle,
        ),
        content=content,
    )


@app.after_request
def log_response(response):
    access_logger.info(f'{request.remote_addr} - {request.method} {request.path} - {response.status_code}')
    return response


def fetch_and_convert_image(image_url, max_width=200):
    try:
        resp = requests.get(image_url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        
        if len(resp.content) > 5 * 1024 * 1024:
            return None
        
        img = Image.open(BytesIO(resp.content))

        
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)
        
        output = BytesIO()
        img.save(output, format='GIF')
        output.seek(0)
        
        return output.getvalue()
    except:
        return None


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