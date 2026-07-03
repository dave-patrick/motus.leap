import pathlib

# Fix playlist name truncation and other issues identified in review
p = pathlib.Path('tube-manager/web/static/playlists.js')
t = p.read_text()

# Fix 1: Replace truncate with break-words for playlist names
t = t.replace('text-white truncate">${p.title}', 'text-white break-words">${p.title}')

# Fix 2: Add alt text to thumbnails for accessibility
t = t.replace('alt="${p.title}"', 'alt="${p.title} thumbnail"')

# Fix 3: Ensure proper button container structure (remove extra closing div)
old_close = '''          </div>
          <button onclick="event.preventDefault(); event.stopPropagation(); openPlaylist('${p.id}', event)" class="text-xs p-1.5 rounded bg-[#20242c] text-gray-400 border border-[#2a2f3a] hover:text-white hover:border-[#374151] transition-colors flex-shrink-0" title="Open on YouTube"><i class="fa-solid fa-external-link text-[10px]"></i></button>
        </a>'''

new_close = '''              <button onclick="event.preventDefault(); event.stopPropagation(); openPlaylist('${p.id}', event)" class="text-xs p-1.5 rounded bg-[#20242c] text-gray-400 border border-[#2a2f3a] hover:text-white hover:border-[#374151] transition-colors flex-shrink-0" title="Open on YouTube"><i class="fa-solid fa-external-link text-[10px]"></i></button>
            </div>
          </div>
        </a>'''

t = t.replace(old_close, new_close)

p.write_text(t)
print("✅ Fixed review issues: playlist names, accessibility, button structure")
