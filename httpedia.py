import os
import requests
import re
import logging
import hashlib
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


MAX_QUERY_LENGTH = 500
MAX_IMAGES = 10
RESULTS_PER_PAGE = 10
MAX_PAGES = 50
MAX_CACHE_SIZE_GB = 90


LOG_DIR = '/var/log/httpedia'
CACHE_DIR = '/var/cache/httpedia/images'
WIKIPEDIA_BASE = 'https://en.wikipedia.org'


DEFAULTS = {
    'skin': 'light',
    'img': '1',
}


HEADERS = {
    'User-Agent': 'HTTPedia/1.0 (https://httpedia.samwarr.dev; minimal Wikipedia proxy for vintage browsers)'
}


DOCTYPE = '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">'


META = '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'


BODY_STYLES = {
    'light': 'bgcolor="#ffffff" text="#000000" link="#0000ee" vlink="#551a8b"',
    'dark': 'bgcolor="#1a1a1a" text="#e0e0e0" link="#6db3f2" vlink="#a0a0ff"'
}


HEADER = '''<center>
<h1>HTTPedia</h1>
<small>
Basic HTML Wikipedia proxy for retro computers. Built by 
<a href="https://github.com/sammothxc/httpedia">
<b>sammothxc</b></a>, 2026.
</small>
<hr>
<small><a href="/{home_query}">Home/Search</a> | 
<a href="{skin_toggle_url}">{skin_toggle_text}</a> | 
<a href="{img_toggle_url}">{img_toggle_text}</a> | 
<a href="https://ko-fi.com/sammothxc">Keep it running</a>
</small>
</center>
<hr>'''


FOOTER = '''<hr>
<center>
<small>
Content sourced from <a href="{wikipedia_url}">this Wikipedia page</a> under 
<a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>.
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
<a href="https://ko-fi.com/sammothxc">Keep it running</a>
</small>
<hr>
<br>
{logo}
<small>
Basic HTML Wikipedia proxy for retro computers. Built by 
<a href="https://github.com/sammothxc/httpedia">
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
<a href="http://frogfind.com">FrogFind</a> | 
<a href="http://68k.news">68k.news</a> | 
<a href="http://textfiles.com/">textfiles.com</a>*
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

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

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
    if img not in ('0', '1', 'a'):
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
    current = prefs['img']
    
    if current == '1':
        new_prefs['img'] = 'a'
        text = 'Images: One'
    elif current == 'a':
        new_prefs['img'] = '0'
        text = 'Images: All'
    else:
        new_prefs['img'] = '1'
        text = 'Images: None'
    
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


def extract_image_path(src):
    if 'upload.wikimedia.org' not in src:
        return None, None

    if '/commons/' in src:
        img_path = src.split('/commons/')[-1]
        prefix = ''
    elif '/en/' in src:
        img_path = src.split('/en/')[-1]
        prefix = 'en/'
    else:
        return None, None

    if not re.match(r'^[a-zA-Z0-9/_.-]+$', img_path) or '..' in img_path:
        return None, None
    
    return prefix, img_path


def extract_article_images(content, title_text, mode, max_images=MAX_IMAGES):
    if mode == '0':
        return '', ''
    
    limit = 1 if mode == '1' else max_images
    images = []
    seen_paths = set()
    
    for img_tag in content.find_all('img', src=True):
        if len(images) >= limit:
            break
        
        src = img_tag.get('src', '')
        prefix, img_path = extract_image_path(src)
        
        if img_path is None:
            continue
        
        full_path = f'{prefix}{img_path}'
        if full_path in seen_paths:
            continue
        seen_paths.add(full_path)
        
        width = img_tag.get('width', '')
        height = img_tag.get('height', '')
        try:
            if width and int(width) < 50:
                continue
            if height and int(height) < 50:
                continue
        except ValueError:
            pass
        
        alt_text = img_tag.get('alt', escape(title_text))
        img_src = f'/img/{prefix}{img_path}'
        images.append(f'<img src="{img_src}" alt="{escape(alt_text)}">')
    
    if not images:
        return '', ''
    
    hero_html = f'<center>{images[0]}</center><br>'
    
    if len(images) > 1:
        gallery_images = ' '.join(images[1:])
        gallery_html = f'<h2>More Images</h2><br><br>{gallery_images}'
    else:
        gallery_html = ''
    
    return hero_html, gallery_html


def extract_infobox(content):
    infobox = content.find(['table', 'div'], class_=re.compile(r'infobox'))
    if not infobox:
        return ''
    
    items = []
    
    rows = infobox.find_all('tr')
    for row in rows:
        label_cell = row.find(['th'], class_=re.compile(r'infobox-label'))
        data_cell = row.find(['td'], class_=re.compile(r'infobox-data'))
        
        if not label_cell:
            label_cell = row.find('th')
        if not data_cell:
            data_cell = row.find('td')
        
        if label_cell and data_cell:
            label = clean_text(label_cell.get_text())
            value = clean_text(data_cell.get_text())
            
            if label and value:
                items.append((label, value))
    
    if not items:
        return ''
    
    html = '<ul>\n'
    for label, value in items:
        html += f'<li><b>{escape(label)}:</b> {escape(value)}</li>\n'
    html += '</ul>\n<hr>\n'
    
    return html


@app.route('/')
def home():
    prefs = get_prefs()
    skin = prefs['skin']
    img = prefs['img']
    prefs_string = build_prefs_string(prefs)
    skin_toggle_params, skin_toggle_text = get_skin_toggle(prefs)
    img_toggle_params, img_toggle_text = get_img_toggle(prefs)

    if img != '0':
        logo = '<img src="/static/httpedia-logo.gif" alt="HTTPedia Logo" width="323" height="65"><br>'
    else:
        logo = '<h1>HTTPedia</h1>'

    input_name = 'q'
    if skin == 'dark':
        input_name += '_dark'
    if img == '0':
        input_name += '_noimg'
    elif img == 'a':
        input_name += '_allimg'

    def build_link(path, text):
        url = f'{path}?{prefs_string}' if prefs_string else path
        return f'<a href="{url}">{text}</a>'

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
    elif request.args.get('q_dark_allimg') is not None:
        query = request.args.get('q_dark_allimg')
        skin = 'dark'
        img = 'a'
    elif request.args.get('q_dark') is not None:
        query = request.args.get('q_dark')
        skin = 'dark'
        img = '1'
    elif request.args.get('q_noimg') is not None:
        query = request.args.get('q_noimg')
        skin = 'light'
        img = '0'
    elif request.args.get('q_allimg') is not None:
        query = request.args.get('q_allimg')
        skin = 'light'
        img = 'a'
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
    
    page = request.args.get('page', '1')
    try:
        page = int(page)
        if page < 1:
            page = 1
        if page > MAX_PAGES:
            page = MAX_PAGES
    except ValueError:
        page = 1
    
    prefs_string = build_prefs_string(prefs)
    
    all_results = search_wikipedia(query)
    total_results = len(all_results)
    total_pages = min((total_results + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE, MAX_PAGES)
    
    start_idx = (page - 1) * RESULTS_PER_PAGE
    end_idx = start_idx + RESULTS_PER_PAGE
    results = all_results[start_idx:end_idx]
    
    wikipedia_url = f'{WIKIPEDIA_BASE}/wiki/Special:Search?search={quote_plus(query)}'
    title_text = f'Search: {escape(query)}'

    if not all_results:
        content = '<p>No results found.</p>'
    else:
        content = f'<center><p>Search Results for <b>{escape(query)}</b></p></center><ul>\n'
        for r in results:
            title_slug = quote(r['title'].replace(' ', '_'), safe='')
            url = f'/wiki/{title_slug}?{prefs_string}' if prefs_string else f'/wiki/{title_slug}'
            snippet = r['snippet'] if r['snippet'] else 'No description available.'
            content += f'<li><a href="{url}">{escape(r["title"])}</a> - {escape(snippet)}</li>\n'
        content += '</ul>'
        
        if total_pages > 1:
            content += '<hr><center>Page: '
            for p in range(1, total_pages + 1):
                if p == page:
                    content += f'<b>[{p}]</b> '
                else:
                    page_params = f'q={quote_plus(query)}&page={p}'
                    if prefs_string:
                        page_params += f'&{prefs_string}'
                    content += f'<a href="/search?{page_params}">{p}</a> '
            content += '</center>'

    return PAGE_TEMPLATE.format(
        doctype=DOCTYPE,
        meta=META,
        title_text=title_text,
        body_style=BODY_STYLES.get(skin, BODY_STYLES['light']),
        header=render_header('/search', prefs, f'q={quote_plus(query)}&page={page}'),
        content=content,
        footer=FOOTER.format(wikipedia_url=wikipedia_url),
    )


def search_wikipedia(query, limit=499):
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
    img_mode = prefs['img']
    prefs_string = build_prefs_string(prefs)

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
    
    infobox_html = extract_infobox(content)
    hero_image, gallery_html = extract_article_images(content, title_text, img_mode)
    
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
    body_content += hero_image
    body_content += infobox_html
    body_content += process_content(content, prefs_string)
    body_content += gallery_html

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
@limiter.limit("10 per second")
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
<p>HTTPedia is a lightweight <a href="https://wikipedia.org">Wikipedia.org</a> proxy designed for vintage computers and retro web browsers
that can no longer use most of the modern web as it is.</p>

<p>Modern Wikipedia is filled JavaScript, complex CSS, high-resolution images, and it makes use of lots of 
modern browser features that old machines can't handle. HTTPedia strips all that away and serves clean HTML 3.2 that works 
on browsers from the 1990s and earlier. In addition to cutting down on complexity, HTTPedia is served over HTTP meaning 
there are no minimum HTTPS or TLS requirements.</p>

<h3>Features</h3>
<p>
- No HTTPS required! Works on machines that can't handle modern TLS
- Pure, <a href="https://validator.w3.org/check?uri=http%3A%2F%2Fhttpedia.samwarr.net%2F">
validated HTML 3.2 output</a> (no JavaScript or CSS)<br>
- All images converted to GIFs for compatibility<br>
- Light and dark modes<br>
- Option to load one, all, or disable images entirely<br>
- Works on Netscape, Mosaic, early IE, text browsers, even Microweb on an 8088!
- [COMING SOON] Support for multiple languages
</p>

<h3>So... Why?</h3>
<p>Because old computers deserve to access information too!</p>
<p><strong>
Want to help out?</strong> 
<a href="https://github.com/sammothxc/httpedia">Leave feedback on the project on GitHub</a>
or 
<a href="https://ko-fi.com/sammothxc">donate to keep the server running.</a>
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
    cache_key = hashlib.md5(image_url.encode()).hexdigest() + '.gif'
    cache_path = os.path.join(CACHE_DIR, cache_key)
    use_cache = not app.debug
    
    if use_cache and os.path.exists(cache_path):
        try:
            with open(cache_path, 'rb') as f:
                app.logger.info(f'Cache hit: {cache_key}')
                return f.read()
        except Exception:
            pass
    
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
        gif_data = output.getvalue()
        
        if use_cache:
            try:
                with open(cache_path, 'wb') as f:
                    f.write(gif_data)
            except Exception as e:
                app.logger.debug(f'Failed to cache image: {e}')
        
        return gif_data
    
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
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=80, debug=debug)