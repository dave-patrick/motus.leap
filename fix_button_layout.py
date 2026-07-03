import pathlib

# Fix button layout in playlists.js - YouTube button not properly nested
p = pathlib.Path('tube-manager/web/static/playlists.js')
t = p.read_text()

# Fix the button structure - move YouTube button inside the flex container
old_structure = '''            <div class="flex items-center gap-2 mt-1" onclick="event.stopPropagation()">
              <button onclick="event.preventDefault(); event.stopPropagation(); rescanPlaylist('${p.id}', event)" class="bg-[#20242c] hover:bg-[#2a2f3a] border border-[#2a2f3a] text-gray-300 text-xs py-1.5 px-2 rounded transition-colors" title="Rescan Videos"><i class="fa-solid fa-arrows-rotate text-[10px]"></i></button>
            </div>
              <button onclick="event.preventDefault(); event.stopPropagation(); openPlaylist('${p.id}', event)" class="text-xs p-1.5 rounded bg-[#20242c] text-gray-400 border border-[#2a2f3a] hover:text-white hover:border-[#374151] transition-colors flex-shrink-0" title="Open on YouTube"><i class="fa-solid fa-external-link text-[10px]"></i></button>
            </div>'''

new_structure = '''            <div class="flex items-center gap-2 mt-1" onclick="event.stopPropagation()">
              <button onclick="event.preventDefault(); event.stopPropagation(); rescanPlaylist('${p.id}', event)" class="bg-[#20242c] hover:bg-[#2a2f3a] border border-[#2a2f3a] text-gray-300 text-xs py-1.5 px-2 rounded transition-colors" title="Rescan Videos"><i class="fa-solid fa-arrows-rotate text-[10px]"></i></button>
              <button onclick="event.preventDefault(); event.stopPropagation(); openPlaylist('${p.id}', event)" class="text-xs p-1.5 rounded bg-[#20242c] text-gray-400 border border-[#2a2f3a] hover:text-white hover:border-[#374151] transition-colors flex-shrink-0" title="Open on YouTube"><i class="fa-solid fa-external-link text-[10px]"></i></button>
            </div>'''

t = t.replace(old_structure, new_structure)
p.write_text(t)
print("✅ Fixed button layout - both buttons properly nested in flex container")
