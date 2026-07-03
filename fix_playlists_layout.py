import pathlib

# Fix playlist name layout in playlists.js
p = pathlib.Path('tube-manager/web/static/playlists.js')
t = p.read_text()

# Fix playlist name layout to be above icon and full width
old_layout = '''            <div class="flex items-center gap-2 mt-1" onclick="event.stopPropagation()">
              <button onclick="event.preventDefault(); event.stopPropagation(); rescanPlaylist('${p.id}', event)" class="bg-[#20242c] hover:bg-[#2a2f3a] border border-[#2a2f3a] text-gray-300 text-xs py-1.5 px-2 rounded transition-colors" title="Rescan Videos"><i class="fa-solid fa-arrows-rotate text-[10px]"></i></button>
              <button onclick="event.preventDefault(); event.stopPropagation(); openPlaylist('${p.id}', event)" class="text-xs p-1.5 rounded bg-[#20242c] text-gray-400 border border-[#2a2f3a] hover:text-white hover:border-[#374151] transition-colors flex-shrink-0" title="Open on YouTube"><i class="fa-solid fa-external-link text-[10px]"></i></button>
            </div>
          </div>'''

new_layout = '''            <div class="flex items-center gap-2 mt-1" onclick="event.stopPropagation()">
              <button onclick="event.preventDefault(); event.stopPropagation(); rescanPlaylist('${p.id}', event)" class="bg-[#20242c] hover:bg-[#2a2f3a] border border-[#2a2f3a] text-gray-300 text-xs py-1.5 px-2 rounded transition-colors" title="Rescan Videos"><i class="fa-solid fa-arrows-rotate text-[10px]"></i></button>
              <button onclick="event.preventDefault(); event.stopPropagation(); openPlaylist('${p.id}', event)" class="text-xs p-1.5 rounded bg-[#20242c] text-gray-400 border border-[#2a2f3a] hover:text-white hover:border-[#374151] transition-colors flex-shrink-0" title="Open on YouTube"><i class="fa-solid fa-external-link text-[10px]"></i></button>
            </div>
          </div>'''

# Also fix the card structure to ensure name takes full width
old_card = '''          <div class="flex items-start gap-2 flex-1 min-w-0">
            <img src="${p.thumbnail || 'https://img.youtube.com/vi/default/medium.jpg'}" alt="${p.title}" class="w-12 h-12 rounded object-cover flex-shrink-0" onerror="this.src='https://img.youtube.com/vi/default/medium.jpg'" />
            <div class="flex-1 min-w-0">
              <h3 class="text-sm md:text-base font-semibold text-white truncate">${p.title}</h3>
              <p class="text-xs text-gray-400">${p.video_count} videos</p>'''

new_card = '''          <div class="flex items-start gap-2 flex-1 min-w-0">
            <img src="${p.thumbnail || 'https://img.youtube.com/vi/default/medium.jpg'}" alt="${p.title}" class="w-12 h-12 rounded object-cover flex-shrink-0" onerror="this.src='https://img.youtube.com/vi/default/medium.jpg'" />
            <div class="flex-1 min-w-0">
              <h3 class="text-sm md:text-base font-semibold text-white break-words">${p.title}</h3>
              <p class="text-xs text-gray-400">${p.video_count} videos</p>'''

t = t.replace(old_card, new_card)
t = t.replace(old_layout, new_layout)
p.write_text(t)
print("✅ Fixed playlist name layout - no truncation, full width")
