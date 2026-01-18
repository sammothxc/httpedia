import os
import requests
import re
import logging
from logging.handlers import RotatingFileHandler
from urllib.parse import quote, quote_plus
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

MAX_QUERY_LENGTH = 500


WIKIPEDIA_BASE = 'https://en.wikipedia.org'


HEADERS = {
    'User-Agent': 'HTTPedia/1.0 (https://httpedia.samwarr.dev; minimal Wikipedia proxy for vintage browsers)'
}


DOCTYPE = '<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">'


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
<small><a href="/{home_query}">Home/Search</a> | 
<a href="{skin_toggle_url}">{skin_toggle_text}</a> | 
<a href="{img_toggle_url}">{img_toggle_text}</a> | 
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
<title>What is HTTPedia?</title>
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
    skin, img = validate_prefs(skin, img)
    return {'skin': skin, 'img': img}


def validate_prefs(skin, img):
    if skin not in ('light', 'dark'):
        skin = 'light'
    if img not in ('0', '1'):
        img = '1'
    return skin, img


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


def build_toggle_url(base_path, toggle_params, extra_params=''):
    params = toggle_params
    if extra_params:
        if params:
            params = f'{params}&{extra_params}'
        else:
            params = extra_params
    if params:
        return f'{base_path}?{params}'
    return base_path


def render_header(base_path, prefs, extra_params=''):
    prefs_string = build_prefs_string(prefs)
    skin_toggle_params, skin_toggle_text = get_skin_toggle(prefs)
    img_toggle_params, img_toggle_text = get_img_toggle(prefs)
    
    home_query = f'?{prefs_string}' if prefs_string else ''
    
    skin_toggle_url = build_toggle_url(base_path, skin_toggle_params, extra_params)
    img_toggle_url = build_toggle_url(base_path, img_toggle_params, extra_params)
    
    return HEADER.format(
        home_query=home_query,
        skin_toggle_url=skin_toggle_url,
        skin_toggle_text=skin_toggle_text,
        img_toggle_url=img_toggle_url,
        img_toggle_text=img_toggle_text,
    )


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

    # i am pretty proud of this workaround for not being able to use `input type="hidden"` in Microweb
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
    
    skin, img = validate_prefs(skin, img)
    prefs = {'skin': skin, 'img': img}
    
    if not query:
        prefs_string = build_prefs_string(prefs)
        return redirect(f'/?{prefs_string}' if prefs_string else '/')
    
    if len(query) > MAX_QUERY_LENGTH:
        query = query[:MAX_QUERY_LENGTH]
    
    prefs_string = build_prefs_string(prefs)
    
    results = search_wikipedia(query)
    
    wikipedia_url = f'{WIKIPEDIA_BASE}/wiki/Special:Search?search={quote_plus(query)}'
    title_text = f'Search: {escape(query)}'

    if not results:
        content = '<p>No results found.</p>'
    else:
        content = f'<center><p>Search Results for <b>{escape(query)}</b></p></center><ul>\n'
        for r in results:
            title_slug = quote(r['title'].replace(' ', '_'), safe='')
            url = f'/wiki/{title_slug}?{prefs_string}' if prefs_string else f'/wiki/{title_slug}'
            snippet = r['snippet'] if r['snippet'] else 'No description available.'
            content += f'<li><a href="{url}">{escape(r["title"])}</a> - {escape(snippet)}</li>\n'
        content += '</ul>'

    return PAGE_TEMPLATE.format(
        doctype=DOCTYPE,
        meta=META,
        title_text=title_text,
        body_style=BODY_STYLES.get(skin, BODY_STYLES['light']),
        header=render_header('/search', prefs, f'q={quote_plus(query)}'),
        content=content,
        footer=FOOTER.format(wikipedia_url=wikipedia_url),
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

    except Exception as e:
        app.logger.warning(f'Wikipedia search failed: {e}')
        return []


@app.route('/wiki/<path:title>')
def wiki(title):
    if not re.match(r'^[\w\s\-.,()\'\"&:;!/#+%@]+$', title, re.UNICODE):
        return Response(render_error('Invalid article title'), mimetype='text/html'), 400
    
    if len(title) > 500:
        return Response(render_error('Article title too long'), mimetype='text/html'), 400
    
    prefs = get_prefs()
    skin = prefs['skin']
    img_enabled = prefs['img'] == '1'
    prefs_string = build_prefs_string(prefs)

    try:
        resp = requests.get(f'{WIKIPEDIA_BASE}/wiki/{quote(title, safe="")}', headers=HEADERS, timeout=10)
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
                    if re.match(r'^[a-zA-Z0-9/_.-]+$', img_path) and '..' not in img_path:
                        article_image = f'<center><img src="/img/{img_path}" alt="{escape(title_text)}"></center><br>'
                elif '/en/' in src:
                    img_path = src.split('/en/')[-1]
                    if re.match(r'^[a-zA-Z0-9/_.-]+$', img_path) and '..' not in img_path:
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

    wikipedia_url = f'{WIKIPEDIA_BASE}/wiki/{quote(title, safe="")}'

    return PAGE_TEMPLATE.format(
        doctype=DOCTYPE,
        meta=META,
        title_text=escape(title_text),
        body_style=BODY_STYLES.get(skin, BODY_STYLES['light']),
        header=render_header(f'/wiki/{quote(title, safe="")}', prefs),
        content=body_content,
        footer=FOOTER.format(wikipedia_url=wikipedia_url),
    )


@app.route('/img/<path:image_path>')
@limiter.limit("1 per 5 seconds")   # for now
def proxy_image(image_path):
    prefs = get_prefs()
    if prefs['img'] == '0':
        return Response(b'GIF89a\x01\x00\x01\x00\x00\x00\x00!', mimetype='image/gif')
    
    if not re.match(r'^[a-zA-Z0-9/_.-]+$', image_path):
        return Response(b'', status=400)
    
    if '..' in image_path:
        return Response(b'', status=400)
    
    if len(image_path) > 500:
        return Response(b'', status=400)
    
    if image_path.startswith('en/'):
        image_url = f'https://upload.wikimedia.org/wikipedia/{image_path}'
    else:
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
<p><strong>
Want to help out?</strong> 
<a href="https://github.com/sammothxc/httpedia" target="_blank">Leave feedback on the project on GitHub</a>
or 
<a href="https://ko-fi.com/sammothxc" target="_blank">donate to keep the server running.</a>
</p>
'''

    return ABOUT_TEMPLATE.format(
        doctype=DOCTYPE,
        meta=META,
        body_style=BODY_STYLES.get(skin, BODY_STYLES['light']),
        header=render_header('/about', prefs),
        content=content,
    )


@app.after_request
def log_response(response):
    access_logger.info(f'{request.remote_addr} - {request.method} {request.path} - {response.status_code}')
    return response


@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # no csp, it breaks several browsers
    return response


def fetch_and_convert_image(image_url, max_width=200):
    try:
        resp = requests.get(image_url, headers=HEADERS, timeout=10, stream=True)
        resp.raise_for_status()
        
        content_length = resp.headers.get('Content-Length')
        if content_length and int(content_length) > 5 * 1024 * 1024:
            return None
        
        content = resp.content
        if len(content) > 5 * 1024 * 1024:
            return None
        
        img = Image.open(BytesIO(content))

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
    
    except Exception as e:
        app.logger.debug(f'Image conversion failed for {image_url}: {e}')
        return None


def render_error(message):
    return ERROR_TEMPLATE.format(
        doctype=DOCTYPE,
        meta=META,
        message=escape(message)
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
                lines.append(f'<{child.name}>{escape(text)}</{child.name}>')

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
                    lines.append(f'<p><b>{escape(clean_text(item.get_text()))}</b></p>')
                elif item.name == 'dd':
                    html = process_paragraph(item, prefs)
                    if html.strip():
                        lines.append(f'<p>{html}</p>')

        elif child.name == 'blockquote':
            text = clean_text(child.get_text())
            if text.strip():
                lines.append(f'<blockquote>{escape(text)}</blockquote>')

        elif child.name == 'div':
            if 'mw-heading' in child.get('class', []):
                for h in child.find_all(['h2', 'h3', 'h4', 'h5', 'h6'], recursive=False):
                    text = clean_text(h.get_text())
                    text = re.sub(r'\[edit\]', '', text).strip()
                    if text:
                        lines.append(f'<{h.name}>{escape(text)}</{h.name}>')
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
                safe_href = escape(href)
                if prefs:
                    result.append(f'<a href="{safe_href}?{prefs}">{escape(text)}</a>')
                else:
                    result.append(f'<a href="{safe_href}">{escape(text)}</a>')

        
        elif child.name == 'b' or child.name == 'strong':
            text = child.get_text()
            if text.strip():
                result.append(escape(text))
        
        elif child.name == 'i' or child.name == 'em':
            text = child.get_text()
            if text.strip():
                result.append(f'<i>{escape(text)}</i>')
        
        elif child.name == 'br':
            result.append('<br>')
        
        elif child.name in ['span', 'small', 'sup', 'sub']:
            result.append(process_paragraph(child, prefs))
        
        elif child.string:
            result.append(escape(re.sub(r'\s+', ' ', child.string)))
        
        elif hasattr(child, 'get_text'):
            result.append(escape(re.sub(r'\s+', ' ', child.get_text())))
    
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