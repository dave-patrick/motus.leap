# YouTube Playlist Agent

An automated agent for managing YouTube playlists using browser automation. This is specifically designed to bypass YouTube API quota limitations and can be easily integrated into other AI systems.

## Prerequisites

1. Python 3.9+
2. Chromium browser (installed automatically via Playwright)

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **First-time Authentication**: You must log in to your YouTube account once so the agent can save your session data.
   ```bash
   python auth_setup.py
   ```
   A browser window will open. Navigate to YouTube, log in, and close the browser when done. The session will be saved locally.

## Usage for other AIs

This agent provides two interfaces for integration.

### 1. Command Line Interface (CLI)

You can call the agent directly via the terminal:

```bash
# Add a video to a playlist
python cli.py add "https://www.youtube.com/watch?v=dQw4w9WgXcQ" "My Awesome Playlist"

# Remove a video from a playlist
python cli.py remove "https://www.youtube.com/watch?v=dQw4w9WgXcQ" "My Awesome Playlist"

# Create a new playlist with a video
python cli.py create "https://www.youtube.com/watch?v=dQw4w9WgXcQ" "Brand New Playlist"
```

### 2. REST API

Alternatively, you can start the local server and interact via HTTP requests.

Start the server:
```bash
python server.py
```
*(Runs on `http://127.0.0.1:8000`)*

**Endpoints:**
- `POST /add`
- `POST /remove`
- `POST /create`

**Request Body (JSON):**
```json
{
  "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "playlist_name": "My Awesome Playlist"
}
```

## Note on Reliability
Because this uses browser automation (Playwright), it simulates a real user clicking buttons. If YouTube changes its User Interface (e.g. changing the label of the "Save" button), the `core.py` script might need to be updated.
