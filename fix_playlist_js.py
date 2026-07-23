import pathlib

# Fix the null container issue in playlist.js
p = pathlib.Path('tube-manager/web/static/playlist.js')
t = p.read_text()

# Add null check to renderVideos function
old_render = '''function renderVideos() {
    const container = document.getElementById('videos-container');
    if (!allVideos.length) {
        container.innerHTML = '<div class="text-center p-8 text-gray-400">No videos in this playlist</div>';
        return;
    }
    container.innerHTML = `'''

new_render = '''function renderVideos() {
    const container = document.getElementById('videos-container');
    if (!container) {
        console.error('Videos container not found');
        return;
    }
    if (!allVideos.length) {
        container.innerHTML = '<div class="text-center p-8 text-gray-400">No videos in this playlist</div>';
        return;
    }
    container.innerHTML = `'''

t = t.replace(old_render, new_render)
p.write_text(t)
print("✅ Fixed playlist.js null container error")
