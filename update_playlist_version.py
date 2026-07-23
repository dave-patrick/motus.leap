import re
import pathlib
import time

# Update playlist.js version in playlist.html
playlist_html = pathlib.Path('tube-manager/web/playlist.html')
content = playlist_html.read_text()

# Update version parameter with current timestamp
current_time = int(time.time())
content = re.sub(r'src="/static/playlist\.js\?v=[0-9]+"', f'src="/static/playlist.js?v={current_time}"', content)

playlist_html.write_text(content)
print(f"Updated playlist.js version to {current_time}")
