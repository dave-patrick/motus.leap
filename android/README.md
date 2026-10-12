# motus.leap for Android

Native Android client for the existing motus.leap FastAPI backend. This first
version supports Google-only login, scans, reviewed AI sorting, library
overview, playlist and channel browsing, read-only channel mappings, refresh,
sign-out, and opening playlists and channels in YouTube. The screens are Android
views, not a WebView.

Scans is the initial destination: queue playlist sync, full library scan,
duplicate scan, or misplaced-video scan, then refresh task status and view the
server's maintenance findings. Queued work is labeled as queued, not completed.

AI sort lets you choose a source playlist and video, sends its real title,
channel, and description to the configured server AI, and displays the suggested
destination. Each move requires explicit review and confirmation and offers a
server operation-status screen with success/failure counts. Unknown or ambiguous
playlist names cannot trigger a move. Nothing is automatically moved.

## Build

Install Android SDK platform 36 and use JDK 17 or newer. Set `sdk.dir` in
`local.properties` or set `ANDROID_HOME`, then run in PowerShell:

```powershell
./gradlew.bat assembleDebug lintDebug
```

APK: `app/build/outputs/apk/debug/app-debug.apk`. Open this directory in Android
Studio to run an emulator. Minimum supported Android version is 8.0 (API 26).

## Connect

Enter the HTTPS address of your existing server and tap **Continue with Google**.
Your system browser handles Google authentication and returns to the app with a
single-use code. The app redeems it using its private S256 verifier. The existing
Google web OAuth client and registered HTTPS callback are reused; no Google client
secret or bearer token is embedded in the APK or redirect URL.

The Android app has no email, username, or password sign-in form.
The initial suggested address comes from the repository README; it can be changed
before login. No live-server availability is implied by that default.

Only the server address is saved. Bearer tokens are kept in memory;
restarting the process requires login. The app uses Android's system TLS trust,
does not follow API redirects, and does not permit plain HTTP servers. Server
errors are displayed with a retry action. Expired sessions return to sign-in.

Initial YouTube OAuth connection, account registration, and server configuration
currently use the account website in the system browser. Google login uses
`/api/auth/mobile/google` and `/api/auth/mobile/exchange`; an older server without
those endpoints must be updated. A sign-in must complete within five minutes and
its returned code must be redeemed within one minute. Expired attempts can be
restarted. The app uses the current website's original icon and dark blue branding.

The backend handoff store is in memory and supports the current single-process
Render deployment. Multiple workers or replicas need a shared, atomic TTL store.

## Current scope

Playlist editing, mapping editing, batch AI sorting, automatic job polling,
persistent encrypted sessions and full video detail screens are follow-up work.
Mappings currently show server identifiers. The server remains responsible for
YouTube credentials and all background processing. No server secrets belong in
the APK. The backend was not modified for this client.

Version 0.3.0 uses Material 3 controls and navigation with Yomu's dark surface,
muted text, rounded shapes, and pale blue accent as the visual reference. Server
configuration is collapsed on the Google-only welcome screen. The original
motus.leap artwork is retained.

Version 0.4.0 uses a clean text wordmark on welcome and authenticated screens,
adds filtering of loaded playlist/channel/video lists, and retains recovery
actions for failed or ambiguous AI suggestions. Scan findings show video titles,
playlist context and reasons, with an explicit link to website review before
any changes. Google OAuth and reviewed move behavior are unchanged.

## Validation limits

Build and lint validate packaging and static Android compatibility. Live login,
YouTube scans, AI suggestions, and moves need a configured server account and
device/emulator verification. No live scan or playlist mutation is performed by
the build. Current UI copy is English only.
