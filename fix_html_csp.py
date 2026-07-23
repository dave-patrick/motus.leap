import pathlib

# Fix CSP meta tag in playlists.html
p = pathlib.Path('tube-manager/web/playlists.html')
t = p.read_text()

# Remove the invalid static script sources from CSP meta tag
old_csp = '''<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com /static/ux-enhancements.js?v=1781919149 /static/auth-check.js?v=1781919149 /static/playlists.js; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; img-src 'self' data: https:; connect-src 'self' wss: https:; frame-ancestors 'self';">'''

new_csp = '''<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; img-src 'self' data: https:; connect-src 'self' wss: https:;">'''

t = t.replace(old_csp, new_csp)

p.write_text(t)
print("✅ Fixed CSP meta tag in playlists.html")
