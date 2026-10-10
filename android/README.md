# motus.leap for Android

Native Android client for the existing motus.leap FastAPI backend. This first
version supports Google and username/password login, scans, reviewed AI sorting, library
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

Username/password login is also available for accounts that use it.
The initial suggested address comes from the repository README; it can be changed
before login. No live-server availability is implied by that default.

Only the server address is saved. Passwords and bearer tokens are kept in memory;
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
persistent encrypted sessions, search, and full video detail screens are follow-up work.
Mappings currently show server identifiers. The server remains responsible for
YouTube credentials and all background processing. No server secrets belong in
the APK. The backend was not modified for this client.

## Validation limits

Build and lint validate packaging and static Android compatibility. Live login,
YouTube scans, AI suggestions, and moves need a configured server account and
device/emulator verification. No live scan or playlist mutation is performed by
the build. Current UI copy is English only.
