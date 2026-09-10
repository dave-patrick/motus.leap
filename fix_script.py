import os
import re
import glob

# Q1: core/utils.py fast json
utils_path = 'core/utils.py'
with open(utils_path, 'r', encoding='utf-8') as f:
    utils_code = f.read()

if 'def fast_dumps' not in utils_code:
    fast_json_code = '''
try:
    import orjson
    def fast_dumps(obj, **kwargs):
        return orjson.dumps(obj).decode('utf-8')
except ImportError:
    def fast_dumps(obj, **kwargs):
        if 'indent' in kwargs:
            return json.dumps(obj, **kwargs)
        return json.dumps(obj)
'''
    with open(utils_path, 'w', encoding='utf-8') as f:
        f.write(utils_code.replace('import json', 'import json' + fast_json_code))

# Q1: replace json.dumps in background_worker.py
bg_path = 'services/background_worker.py'
with open(bg_path, 'r', encoding='utf-8') as f:
    bg_code = f.read()
if 'from core.utils import fast_dumps' not in bg_code:
    bg_code = bg_code.replace('import json', 'import json\nfrom core.utils import fast_dumps')
bg_code = bg_code.replace('json.dumps', 'fast_dumps')
with open(bg_path, 'w', encoding='utf-8') as f:
    f.write(bg_code)

# Q1: replace json.dumps in app.py
app_path = 'app.py'
with open(app_path, 'r', encoding='utf-8') as f:
    app_code = f.read()
if 'from core.utils import fast_dumps' not in app_code:
    app_code = app_code.replace('import json', 'import json\nfrom core.utils import fast_dumps')
app_code = app_code.replace('json.dumps', 'fast_dumps')
with open(app_path, 'w', encoding='utf-8') as f:
    f.write(app_code)

# Q3: jitter in dashboard.js
js_path = 'web/static/dashboard.js'
with open(js_path, 'r', encoding='utf-8') as f:
    js_code = f.read()
js_code = js_code.replace('}, 30000);', '}, 25000 + Math.random() * 10000);')
with open(js_path, 'w', encoding='utf-8') as f:
    f.write(js_code)

# Q2: check Tailwind CDN
for html_path in glob.glob('web/**/*.html', recursive=True):
    with open(html_path, 'r', encoding='utf-8') as f:
        html_code = f.read()
    if '<script src="https://cdn.tailwindcss.com"></script>' in html_code:
        new_code = html_code.replace(
            '<script src="https://cdn.tailwindcss.com"></script>',
            '<link rel="preconnect" href="https://cdn.tailwindcss.com">\n<script src="https://cdn.tailwindcss.com" defer></script>'
        )
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(new_code)

for html_path in glob.glob('*.html', recursive=True):
    with open(html_path, 'r', encoding='utf-8') as f:
        html_code = f.read()
    if '<script src="https://cdn.tailwindcss.com"></script>' in html_code:
        new_code = html_code.replace(
            '<script src="https://cdn.tailwindcss.com"></script>',
            '<link rel="preconnect" href="https://cdn.tailwindcss.com">\n<script src="https://cdn.tailwindcss.com" defer></script>'
        )
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(new_code)

print('Done')
