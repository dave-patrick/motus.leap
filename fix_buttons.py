#!/usr/bin/env python3
import pathlib

# Fix button layout in playlists.js
p = pathlib.Path('tube-manager/web/static/playlists.js')
t = p.read_text()

# Move YouTube button into the same div as refresh button
old_html = '''          </div>
          <button onclick="event.preventDefault(); event.stopPropagation(); openPlaylist('${p.id}', event)" class="ml-auto text-xs p-1.5 rounded bg-[#20242c] text-gray-400 border border-[#2a2f3a] hover:text-white hover:border-[#374151] transition-colors flex-shrink-0 self-center" title="Open on YouTube"><i class="fa-solid fa-external-link text-[10px]"></i></button>'''
new_html = '''              <button onclick="event.preventDefault(); event.stopPropagation(); openPlaylist('${p.id}', event)" class="text-xs p-1.5 rounded bg-[#20242c] text-gray-400 border border-[#2a2f3a] hover:text-white hover:border-[#374151] transition-colors flex-shrink-0" title="Open on YouTube"><i class="fa-solid fa-external-link text-[10px]"></i></button>
            </div>'''

t = t.replace(old_html, new_html)
p.write_text(t)
print("✅ Fixed button layout - buttons now side by side")
