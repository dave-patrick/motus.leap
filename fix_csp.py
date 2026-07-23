import pathlib

# Fix CSP script sources in app.py
p = pathlib.Path('tube-manager/app.py')
t = p.read_text()

# Fix the script-src sources to match actual static file structure
old_script_src = '''f"script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com /static/dashboard.js /static/subscriptions.js /static/auth-check.js /static/ux-enhancements.js /static/global_scripts.js /static/playlists.js /static/playlist.js /static/mobile-nav.js; "'''

new_script_src = '''f"script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com; "'''

t = t.replace(old_script_src, new_script_src)

# Also remove the browsing-topics from Permissions-Policy
old_permissions = '''f"Permissions-Policy" = "geolocation=(), microphone=(), camera=()"'''
new_permissions = '''f"Permissions-Policy" = "geolocation=(), microphone=(), camera=(), browsing-topics=()"'''

t = t.replace(old_permissions, new_permissions)

p.write_text(t)
print("✅ Fixed CSP script sources and browsing-topics policy")
