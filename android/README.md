# motus.leap for Android

Native Android client for the existing motus.leap FastAPI backend. This first
version supports Google-only login, scans, reviewed AI sorting, library
overview, playlist and channel browsing, read-only channel mappings, refresh,
sign-out, and opening playlists and channels in YouTube. The screens are Android
views, not a WebView.

Dashboard is the initial destination, with activity and quota information. In Scans, queue playlist sync, full library scan,
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

APK: `app/build/outputs/apk/debug/app-debug.apk`.

### Release builds

Public downloads are release-signed, never debug builds. The release key lives outside the repository in `~/.motus-leap-signing/` (`motus-leap-release.jks` plus `keystore.properties` with `storeFile`, `storePassword`, `keyAlias`, `keyPassword`). Point `MOTUS_SIGNING_PROPERTIES` at another properties file if needed. Then run:

```powershell
./gradlew.bat assembleRelease lintRelease
```

Output: `app/build/outputs/apk/release/app-release.apk`. Verify with `apksigner verify --print-certs`; the certificate SHA-256 must be `2325b2875c6b507c157de7fd0f8172b3a1898df341ad63f0e5f5def15610f414`. Every future update must be signed with this same key: back up the folder and never commit it. Without the properties file the release build is unsigned and must not be published. Open this directory in Android
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

The server address and encrypted session are saved. Android Keystore protects the bearer token, bound to the server address; the session is restored until it expires or you sign out. The app uses Android's system TLS trust,
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

Version 0.4.1 restores the existing symbol and Deltha wordmark on welcome and
authenticated headers. Scans includes Move Watch Later to 1~Sort with explicit
confirmation, a background operation and progress/failure counts. YouTube must
confirm the target copy before the Watch Later entry is removed. The server
requires an authenticated YouTube browser session to read/remove Watch Later.

Build and lint validate packaging and static Android compatibility. Live login,
YouTube scans, AI suggestions, and moves need a configured server account and
device/emulator verification. No live scan or playlist mutation is performed by
the build. Current UI copy is English only.

Android 0.4.0 restores Keystore-encrypted sessions across launches and clears them on sign-out or HTTP 401. Settings is in bottom navigation. Scan status refreshes every five seconds while visible, with links to individual findings. Launcher uses the dark brand symbol. SessionTestRunner exercises restoration, encrypted storage, server binding, tamper rejection, and sign-out using isolated test preferences.


Version 0.4.1 opens scan activity immediately after confirmation and routes completed scans to filtered results using server job identity. Duplicate findings expose per-copy removal and keep/dismiss; deleted findings offer confirmed cached cleanup. WordmarkView fits visible glyph bounds to prevent clipped letters.


Version 0.4.2 provides native suggested-move approval, searchable destination selection, keep/dismiss, confirmation, and operation status. Scan findings no longer require website review.

## Release workflow
For every completed Android update: document behavior and validation, commit and push to GitHub, build and lint, install the new APK wirelessly in place on the user's phone, and verify its installed version. Preserve app data. Report edited, pushed, built, installed, and device-verified state separately. If the phone is unavailable, report the install as pending.

## 0.4.2 validation (2026-10-12)
- Android assembleDebug and lintDebug passed.
- Device session checks passed: restore, encrypted storage, server binding, tamper rejection, sign out.
- Real account session survived an in-place reinstall and reopened the library.
- Live scan status loaded; enlarged complete in-app wordmark and bottom Settings gear were visually checked.
- Phone package confirmed versionCode 9 / versionName 0.4.2.
- Watch Later transfer tests: 7 passed.
- Actual playlist removals and suggested-move execution remain unverified. No deletions were executed for validation.

## 0.5.0 — Dashboard and logo
Dashboard is the first destination after sign-in or session restoration, showing library counts, server activity, queued tasks, last scan in local time, and tracked quota. Scan controls and findings are available from Dashboard. Uses the supplied Gemini_Generated_Image_tr.png artwork in-app and for the unframed launcher icon. Build and lint verification and in-place device installation are part of this release.

Validation: Android build/lint passed; v0.5.0 installed in place and Dashboard visually checked with live library counts and retained Google session. The primary full scan button is placed directly beneath library metrics. Other scan controls follow the activity section. No scan or playlist mutation was executed for validation.

0.5.1 matches the user's wordmark reference: white Deltha lettering, blue U (#2F8FC9), muted gray dot (#68717D), and the supplied unframed symbol in header/sign-in. The glyph bounds fitting preserves the complete final P.

